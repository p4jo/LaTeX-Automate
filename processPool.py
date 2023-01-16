#region Imports
# builtin
import itertools
import os
import random
import re
import subprocess
import sys
import time
import contextlib
from datetime import datetime
from pathlib import Path

# quasi builtin
import socket
import asyncio
from asyncio.subprocess import PIPE, Process
import requests
import shutil

# command line interface
import click

# types
from enum import Enum
from abc import ABCMeta, abstractmethod
from typing import Awaitable, Callable, Dict, List, Optional, Union

from win32process import DETACHED_PROCESS
PathOrString = Union[os.PathLike, str]

#endregion

#region constants
ROUTE_OBFUSCATION = 'aosijfoaisdoifnasodnifaosinf'
DEFAULT_PORT = 65012
HALT_LOG = "PAUSED EXECUTION!"
VERBOSE = False

PROCESS_TIMEOUT = 15
WAIT_FOR_COMPLETION_SLEEP_TIME = 0.5
WAIT_FOR_COMPLETION_TIMEOUT = 60
STATE_WATCHER_SLEEP_TIME = 2

MAX_NONSTOP_RUNS = 2
TOO_MANY_NONSTOP_RUNS_COOLDOWN = 180

OLD_TEMP_DIR_TIMEOUT_MIN = 15
BASE_POWERSHELL_COMMAND = """
mkdir "{tempOutputDirectory}";
cp "{outputDirectory}\\{fileName}*" "{tempOutputDirectory}";
$Env:LATEX_ALLOW_PAUSE_EXECUTION="true";
xindex -k "{tempOutputDirectory}\\{fileName}";
biber "{tempOutputDirectory}\\{fileName}";
lualatex --recorder --file-line-error --interaction=nonstopmode --synctex=1 --output-directory="{tempOutputDirectory}" "{fileName}";
cp "{tempOutputDirectory}\\{fileName}*" "{outputDirectory}";
rm -r "{tempOutputDirectory}"
""" #  --max-print-line=300 doesn't work with miktex and lualatex. Add max-print-line=300 to  initexmf --edit-config-file lualatex

THIS_FILE_VERSION_TIME = Path(__file__).stat().st_mtime + 1
#endregion

#region Watcher
class RunnerStates(Enum):
    PREPARING = 0
    WAITING = 1
    RUNNING = 2
    FINISHED = 3

class ErrorStates(Enum):
    NONE = 0
    RETURN_CODE_NONZERO = 1
    NEVER_WAITED = 2
    ABORTED = 3

class Runner(metaclass = ABCMeta):
    def __init__(self) -> None:
        self.lines: List[str] = []
        self.errorState = ErrorStates.NONE

    @abstractmethod
    async def getState(self)->RunnerStates:
        pass
    @abstractmethod
    async def continueRun(self) -> bool:
        pass
    @abstractmethod
    async def updateLog(self):
        pass
    @abstractmethod
    async def stop(self):
        pass
    @staticmethod
    @abstractmethod
    async def newRunner():
        pass

class ProcessWatcher:
    minNumberAvailable = 2

    def __init__(self, newRunnerCallback: Callable[..., Awaitable[Runner]]) -> None:
        self.newRunner = newRunnerCallback

        self.runners: List[Runner] = []
        self.runningRunners: List[Runner] = []
        self.watchTask: asyncio.Task = None
        self.finishResults = {errorState: 0 for errorState in [ErrorStates.NEVER_WAITED, ErrorStates.RETURN_CODE_NONZERO, ErrorStates.NONE, ErrorStates.ABORTED]}        
        self.exited = 0
        self.maxNeverWaitedErrors = MAX_NONSTOP_RUNS

    async def refreshState(self):        
        if self.exited:
            return
        if self.finishResults[ErrorStates.NEVER_WAITED] > self.maxNeverWaitedErrors:
            await self.exit()
            return
        availableRunners: List[Runner] = []
        runningRunners: List[Runner] = []

        for runner in itertools.chain(self.runners, self.runningRunners):
            state = await runner.getState()
            if state == RunnerStates.FINISHED:
                self.finishResults[runner.errorState] += 1
            elif state == RunnerStates.RUNNING:
                runningRunners.append(runner)
            elif state == RunnerStates.WAITING or state == RunnerStates.PREPARING:
                availableRunners.append(runner)
        
        self.runners = availableRunners
        self.runningRunners = runningRunners
        
        for _ in range(len(self.runners), self.minNumberAvailable):
            print(f"Only {len(self.runners)}/{self.minNumberAvailable} runners available, starting a new runner ") #of type", self.T.__name__)
            self.runners.append(await self.newRunner())
        
    async def exit(self):
        print("ABORTING!")
        self.exited = time.time()
        await self.stopWatcher()
        for runner in itertools.chain(self.runners, self.runningRunners):
            await runner.stop()
    
    def unexit(self):
        print("RESUMING!")
        self.exited = 0
        self.maxNeverWaitedErrors += MAX_NONSTOP_RUNS
            
    async def watch(self):
        print("WATCHER STARTED")
        while not self.exited:
            await self.refreshState()
            await asyncio.sleep(STATE_WATCHER_SLEEP_TIME)

    async def runWatcher(self):
        if self.watchTask is None:
            self.watchTask = asyncio.get_running_loop().create_task(self.watch())
            print("Watcher started.")
    
    _watcherStopTimeout = 4
    _watcherStopInterval = 0.1
    async def stopWatcher(self):
        if self.watchTask is None:
            return
        print("Stopping the Watcher ...", end='', flush=True)
        self.watchTask.cancel()
        i = 0
        while not self.watchTask.cancelled() and i < self._watcherStopTimeout/self._watcherStopInterval:
            await asyncio.sleep(0.1)
            i += 1
        if i >= self._watcherStopTimeout/self._watcherStopInterval:
            print(f"WATCHER COULD NOT BE STOPPED IN {self._watcherStopTimeout} s!")
        print("WATCHER STOPPED")
        self.watchTask = None

    async def execute(self, waitForCompletion: bool = False):
        if self.exited:
            if self.exited > time.time() - TOO_MANY_NONSTOP_RUNS_COOLDOWN: 
                print("I already had", self.finishResults[ErrorStates.NONE], "successful compilations", self.finishResults[ErrorStates.RETURN_CODE_NONZERO], "nonzero return codes from runners,", self.finishResults[ErrorStates.ABORTED], "aborted rund and", self.finishResults[ErrorStates.NEVER_WAITED], "runners that never waited. \n ABORTING because that is too much!)" )
                return
            self.unexit()
        else:            
            await self.stopWatcher() # the watcher might currently access the stdout.readline() method. Python throws a RuntimeError when we then also access it.
        
        await self.refreshState() 
        print("Will finish a compilation. I already had", self.finishResults[ErrorStates.NONE], "successful compilations", self.finishResults[ErrorStates.RETURN_CODE_NONZERO], "nonzero return codes from runners, and", self.finishResults[ErrorStates.NEVER_WAITED], "runners that never waited (I will abort after 3)" )

        execute_runner = self.runners[0]
        while True:
            for runner in self.runners: # look for a waiting runner
                if await runner.getState() == RunnerStates.WAITING:
                    execute_runner = runner
                break

            if await execute_runner.continueRun():
                break
            await self.refreshState()

        await self.runWatcher()
        if waitForCompletion:
            i = 0
            while await execute_runner.getState() != RunnerStates.FINISHED and i < WAIT_FOR_COMPLETION_TIMEOUT/WAIT_FOR_COMPLETION_SLEEP_TIME: # let the watcher do the state checking
                await asyncio.sleep(WAIT_FOR_COMPLETION_SLEEP_TIME)
                # await execute_runner.updateLog()
                i += 1

            if i >= WAIT_FOR_COMPLETION_TIMEOUT/WAIT_FOR_COMPLETION_SLEEP_TIME:
                execute_runner.lines.insert(0, f"ABORTED AFTER {WAIT_FOR_COMPLETION_TIMEOUT} SECONDS")
                print(f"ABORTED AFTER {WAIT_FOR_COMPLETION_TIMEOUT} SECONDS.")
                if isinstance(execute_runner, LatexRunner):
                    print("PID", execute_runner.process.pid)
        await execute_runner.updateLog(log = VERBOSE)
        print("Execution finished. PID:", execute_runner.process.pid)
        return "\n".join(execute_runner.lines)

#endregion

#region Runner
class LatexRunner(Runner):

    def __init__(self, info: str, timeoutFunction: Callable[[float], bool]) -> None:
        """ Call the async static method newRunner instead """
        super().__init__()
        self.process: Process = None
        self._state: RunnerStates = None
        self.info = info
        self._creationTime = time.time()
        self._lastLogTime = self._creationTime
        self.timedOut = lambda: timeoutFunction(self._creationTime)

    @staticmethod
    async def newRunner(command: str, workingDirectory: PathOrString = None, info: str = "", timeoutFunction: Callable[[float], bool] = lambda x: False) -> Runner:
        self = LatexRunner(info=info, timeoutFunction=timeoutFunction)
        self.process = await asyncio.create_subprocess_shell(command, stdin=PIPE, stdout=PIPE, cwd=workingDirectory)
        self._state = RunnerStates.PREPARING
        self.lines.append(f"I am a LaTeX runner with PID {self.process.pid} (process ID as seen in the task manager) and command\n\t{command}.")
        print(f"Created new LaTeX runner with PID {self.process.pid} (process ID as seen in the task manager) and command\n\t{command}.")
        return self

    async def checkIfProcessTerminated(self):
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self.process.wait(), 1e-6)
        return self.process.returncode is not None
    
    async def checkIfWaiting(self):
        for line in await self.updateLog(log=VERBOSE):
            if HALT_LOG in line:
                print("This runner has switched to the waiting state! PID:", self.process.pid)
                return True
        return False

    async def getState(self) -> RunnerStates:
        terminated = await self.checkIfProcessTerminated()
        if not terminated:
            startedWaiting = await self.checkIfWaiting() # updates the log and _lastLogTime
            if self._state == RunnerStates.PREPARING and startedWaiting:
                self._state = RunnerStates.WAITING
            # if it starts waiting again after being out of preparing mode -- this is not intended -- so, we just kill it after PROCESS_TIMEOUT seconds below .
            if self._state != RunnerStates.WAITING and \
                    self._lastLogTime < time.time() - PROCESS_TIMEOUT:
                print("-" * 20)
                try:
                    self.process.kill()
                except Exception as e:
                    print("TRIED TO KILL (",e,")", end=' ')
                else:
                    print("KILLED", end = ' ')
                print("RUNNER WITH PID", self.process.pid, "after it didn't output anything for", time.time() -self._lastLogTime, "seconds.")
                print('The last lines of its output are:', *self.lines[-10:] , sep='\n\t')
                print("-" * 20)
                terminated = True

        if self._state != RunnerStates.FINISHED and terminated:
            print(f"A runner has finished with returncode {self.process.returncode}! PID: {self.process.pid}. {self.info}")
            if self._state == RunnerStates.PREPARING:
                self.errorState = ErrorStates.NEVER_WAITED
                print("BUT IT NEVER WAITED! IF THIS HAPPENS TO OFTEN I'LL ABORT. PUT \pauseExecution SOMEWHERE IN YOUR DOCUMENT.")
            elif self.process.returncode != 0:
                self.errorState == ErrorStates.RETURN_CODE_NONZERO
            self._state = RunnerStates.FINISHED

        return self._state
    
    async def continueRun(self) -> bool:
        
        if self.timedOut(): 
            print("Killed an old runner.")
            await self.stop()
            return False

        state = await self.getState() 
        if state == RunnerStates.PREPARING:
            print("Will continue a runner that is still preparing")
            
        while state == RunnerStates.PREPARING:
            await asyncio.sleep(0.4) 
            state = await self.getState() 

        if state == RunnerStates.WAITING:
            print("-----------------------------------------")
            print("Continuing a waiting runner. PID:", self.process.pid)
            print("-----------------------------------------")
            # await readlines_alreadyWritten(self.process)
            self.process.stdin.write(b"\r\n")
            self._state = RunnerStates.RUNNING
            self._lastLogTime = time.time()
            # actually wait for new output
            # await readlines_alreadyWritten(self.process, timeout=1, log=True) # doesn't stop when process is done...
        # await self.getState()
        return True

    async def stop(self):
        if not await self.checkIfProcessTerminated():
            try:
                self.process.kill() 
                self.errorState = ErrorStates.ABORTED
            except ProcessLookupError:
                pass
        self._state = RunnerStates.FINISHED

    async def updateLog(self, timeout: float = 0.05, log: bool = False) -> list:
        """ Loads the latest log messages from the process into self.lines and returns them. Don't call this during execution but call self.getState() because else the program might miss that it switched to the waiting state. """
        lines: List[str] = []
        while self.process.returncode is None:
            try:
                line = (
                    await asyncio.wait_for(
                        self.process.stdout.readline(),
                        timeout = timeout
                    )
                ).decode("utf-8", errors='replace').strip()
                if log:
                    print('\t\t', line)
                lines.append(line)
            except asyncio.TimeoutError:
                # print("Buffered latex log output exceeded! PID:", process.pid)
                break
            except RuntimeError:
                continue
        else:
            lines = (await self.process.stdout.read()).decode('utf-8', errors='replace').splitlines()
        if len(lines) > 0:
            self._lastLogTime = time.time()
            print("\tRead", len(lines), "lines from process", self.process.pid)
            self.lines.extend(lines)
        return lines
#endregion

#region Controlling Watchers and Runners

def newWatcher(texFile: PathOrString, output_dir: PathOrString):
    if texFile is None or texFile == "":
        return None
    texFile = Path(texFile).with_suffix('.tex')
    if not texFile.is_file():
        print("File does not exist")
        return None
    if output_dir is None:
        output_dir = "out"
    outputDirectory = texFile.parent / output_dir

    async def newRunner():
        tempOutputDirectory = getTempOutputDirectory(outputDirectory)
                
        clearOldTempDirectories(tempOutputDirectory.parent)

        return await LatexRunner.newRunner(
            command = getCMDCommand(tempOutputDirectory, outputDirectory,  texFile),
            workingDirectory=texFile.parent,
            info=f"outputDirectory={outputDirectory}, tempOutputDirectory={tempOutputDirectory}",
            timeoutFunction=lambda runnerCreationTime: Path(texFile).stat().st_mtime > runnerCreationTime
        )

    return ProcessWatcher(newRunner)

def clearOldTempDirectories(directory: Path):
    for dir in directory.iterdir():
        if dir.is_dir() and tempFolderRegex.match(dir.name):
            now = datetime.now()
            currentMod = now.hour * 60 + now.minute
            mod = int(dir.name[:2]) * 60 + int(dir.name[3:5])
            if (
                mod > currentMod 
                and
                mod - 24 * 60 < currentMod - OLD_TEMP_DIR_TIMEOUT_MIN      
            ) or (
                mod < currentMod - OLD_TEMP_DIR_TIMEOUT_MIN
            ):
                try:
                    shutil.rmtree(dir)
                except Exception as e:
                    (dir / 'del_error.log').write_text(str(e))

tempFolderRegex = re.compile("^[0-9][0-9]-[0-9][0-9]-[0-9][0-9]")
def getTempOutputDirectory(outputDirectory: Path):
    tempOutputDirectory = outputDirectory / (datetime.now().strftime("%H-%M-%S") + f"({random.randint(1000,9999)})")
    while tempOutputDirectory.exists():
        tempOutputDirectory = tempOutputDirectory.with_name(tempOutputDirectory.name + "_")
    return tempOutputDirectory


def getPowershellCommand(
        tempOutputDirectory: Optional[PathOrString],
        outputDirectory: PathOrString,
        texFile: PathOrString
    ):
    """This command has to be run in the working directory {texFile.parent}"""
    outputDirectory = Path(outputDirectory)
    texFile = Path(texFile)
    if tempOutputDirectory is not None:
        tempOutputDirectory = Path(tempOutputDirectory)
    else:
        tempOutputDirectory = getTempOutputDirectory(outputDirectory)

    return BASE_POWERSHELL_COMMAND \
        .strip() \
        .replace('{outputDirectory}', str(outputDirectory.relative_to( texFile.parent ))) \
        .replace('{tempOutputDirectory}', str(tempOutputDirectory.relative_to( texFile.parent ))) \
        .replace('{fileName}',  texFile.stem) \
        .replace('\n',' ') 

def getCMDCommand(
        tempOutputDirectory: Optional[PathOrString],
        outputDirectory: PathOrString,
        texFile: PathOrString
    ):
    # it is run in cmd, so we need the powershell -c "{...}"
    return 'powershell -c "' + getPowershellCommand(tempOutputDirectory, outputDirectory, texFile).replace('"', '\\"')  + '"'


watchers: Dict[str, ProcessWatcher] = {}

async def do_execute(texFile: str, output_dir: PathOrString = None):
    if texFile is None or texFile == '':
        print("No file path provided!")
        return
    global watchers
    if texFile not in watchers:
        watcher = newWatcher(texFile=texFile, output_dir=output_dir)
        if watcher is None:
            print("Potential Error when creating watcher.")
            return "Potential Error when creating watcher."
        watchers[texFile] = watcher
    else:
        watcher = watchers[texFile]
    return await watcher.execute(waitForCompletion=True)
#endregion

#region Server setup
def runServer(port, texFile: PathOrString = '', output_dir: PathOrString = ''):
    """ Run the server. This never returns, but raises KeyboardInterrupt to kill itself on GET request to f"http://localhost:{port}/stopServer{ROUTE_OBFUSCATION}" """
    from aiohttp import web

    async def handle(request):
        """ the request must come as text of the form 'texFile,outdir' """
        tex_file, outdir = (await request.text()).split(',')
        if Path(__file__).stat().st_mtime > THIS_FILE_VERSION_TIME:
            pid = start_myself_in_background( ['--port', str(port), '--o', str(outdir), '--server', '--f', str(tex_file), '--wait', '10' ] )
            print(f"Restarting myself with PID {pid}.")
            asyncio.create_task( handleStopServer(request) )
            return web.Response(text="Restarting server because of changed server code")
            
        return web.Response(text=await do_execute(tex_file, outdir))

    async def handleStopServer(request):
        try:
            raise KeyboardInterrupt("actually interrupted by call to stopServer")
        finally:
            print("Closed by call to \stopServer---")

    async def startup():
        if texFile != '':
            asyncio.get_event_loop().create_task(
                do_execute(texFile=texFile, output_dir=output_dir) # wrapped in this startup stuff because we only have async from web.run_app
            )
            
        app = web.Application()
        app.add_routes([
            web.post(f'/{ROUTE_OBFUSCATION}', handle),
            web.get(f'/stopServer{ROUTE_OBFUSCATION}', handleStopServer)
        ])
        return app

    web.run_app(startup(), port=port)

def portIsFree(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as testSocket:
        return testSocket.connect_ex(("localhost", port)) != 0
#endregion

def start_myself_in_background(args: List[str]) -> int:
    """ Argument "names" should begin with double dash: single dash arguments are interpreted as options to python (sys.executable) """
    return subprocess.Popen([sys.executable, __file__, *args], creationflags=DETACHED_PROCESS, close_fds=True, shell=False).pid
    
#region main command line interface
@click.command()
@click.option("--tex-file", "--file", "--f", "-f", default="")
@click.option("--output-dir", "--output-directory", "--outdir", "--o", "-o", default="out", help="Path for LaTeX output, relative to the tex file. Every LaTeX runner will use a temporary subdirectory and only copy to this directory in the end. Some files will be copied to our temp dir beforehand.")
@click.option("--port", "--p", "-p", default=DEFAULT_PORT, help=f"The port of/for the server (background worker), default = {DEFAULT_PORT}")
@click.option("--start-server-on-demand/--no-server", "--s,--c", "-s/-c", default=True, help="Start a server in a background process if the port is still free. Enabled by default.")
@click.option("--server", is_flag=True, help="Run the server right here. This script will not end by itself.")
@click.option("--stop-server", is_flag=True, help="Stop the already running server by sending a request. Continue as normal after 1 s.")
@click.option("--print-command", "-c", "--c", "--command", "--pc", "-pc", is_flag=True, help="Only show the powershell command and quit.")
@click.option("--verbose", "-v", "--v", is_flag=True, help="Show the complete output of the child processes.")
@click.option("--wait", "-w", "--w", default = 0, help="Wait for the specified amount of seconds before starting.")
def main(tex_file, output_dir, port, start_server_on_demand, server, stop_server, print_command, verbose, wait):
    if print_command:
        print(getPowershellCommand(None, output_dir, tex_file))
        return
    global VERBOSE
    VERBOSE = verbose
    time.sleep(wait)
    portFree = portIsFree(port)
    if stop_server and not portFree:
        try:
            requests.get(f"http://localhost:{port}/stopServer{ROUTE_OBFUSCATION}")
        except requests.exceptions.ConnectionError: # The server kills itself during this connection
            print("Stopped server.")
        else:
            print("Potentially stopped server.")
        portFree = portIsFree(port)
        if not portFree:
            time.sleep(1)
            portFree = portIsFree(port)
            if not portFree:
                print("SERVER DIDN'T STOP AFTER 1 s")

    if server:
        if portFree:
            runServer(port=port, texFile=tex_file, output_dir=output_dir)
        else:
            print("COULDN'T START THE SERVER, BECAUSE THE PORT IS NOT FREE. IS THERE ANOTHER SERVER RUNNING? KILL IT BY RUNNING THIS AGAIN WITH THE --stop-server FLAG.")
        return

    if tex_file != '' and start_server_on_demand and portFree:
        # command_args = [sys.executable, '"'+__file__+'"', f'--p {port}', f'--o {output_dir}', '--server', f'--f {tex_file}' ]
        # pid = os.spawnl(os.P_NOWAIT, *command_args)
        command_args = [ '--port', str(port), '--o', str(output_dir), '--server', '--f', str(tex_file) ]
        pid = start_myself_in_background(command_args)
        print("STARTED SERVER (BACKGROUND WORKER) WITH PID", pid, "using command ", *command_args)
        print("STOP IT BY CALLING THIS AGAIN WITH THE --stop-server FLAG.")
        print("Your compilation will be done, but you won't see the logs here.")
    if tex_file != '' and not portFree:
        print("Sending request to server (background worker)")
        sendData = (str(tex_file) + ',' + str(output_dir) ).encode('utf8')
        requestResult = requests.post(f"http://localhost:{port}/{ROUTE_OBFUSCATION}", data=sendData)
        content = requestResult.content
        text = content.decode('utf8')
        print(text)
        print("Server finished.")



if __name__ == '__main__':
    main()

#endregion