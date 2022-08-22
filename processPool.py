#region Imports
# builtin
import itertools
import os
import random
import re
import shutil
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

# types
from enum import Enum
from abc import ABCMeta, abstractmethod
from typing import Awaitable, Callable, Dict, List, Optional, Union

from win32process import DETACHED_PROCESS

# command line interface
import click

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

class Runner(metaclass = ABCMeta):
    def __init__(self) -> None:
        self.lines: List[str] = []
        self.errorState = ErrorStates.NONE

    @abstractmethod
    async def getState(self)->RunnerStates:
        pass
    @abstractmethod
    async def continueRun(self):
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
        self.finishResults = {errorState: 0 for errorState in [ErrorStates.NEVER_WAITED, ErrorStates.RETURN_CODE_NONZERO, ErrorStates.NONE]}        
        self.exited = False

    async def refreshState(self):        
        if self.exited:
            return
        if self.finishResults[ErrorStates.NEVER_WAITED] > 2:
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
        self.exited = True
        await self.stopWatcher()
        for runner in itertools.chain(self.runners, self.runningRunners):
            await runner.stop()
            
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
            print("I already had", self.finishResults[ErrorStates.NONE], "successful compilations", self.finishResults[ErrorStates.RETURN_CODE_NONZERO], "nonzero return codes from runners, and", self.finishResults[ErrorStates.NEVER_WAITED], "runners that never waited. \n ABORTING because that is too much!)" )
            return
       
        await self.stopWatcher() # the watcher might currently access the stdout.readline() method. Python throws a RuntimeError when we then also access it.
        await self.refreshState() 
        print("Will finish a compilation. I already had", self.finishResults[ErrorStates.NONE], "successful compilations", self.finishResults[ErrorStates.RETURN_CODE_NONZERO], "nonzero return codes from runners, and", self.finishResults[ErrorStates.NEVER_WAITED], "runners that never waited (I will abort after 3)" )

        execute_runner = self.runners[0]
        for runner in self.runners: # look for a waiting runner
            if await runner.getState() == RunnerStates.WAITING:
               execute_runner = runner
               break

        await execute_runner.continueRun()
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

#region 
class LatexRunner(Runner):

    def __init__(self, info: str) -> None:
        """ Call the async static method newRunner instead """
        super().__init__()
        self.process: Process = None
        self._state: RunnerStates = None
        self.info = info
        self._lastLogTime = 0

    @staticmethod
    async def newRunner(command: str, workingDirectory: PathOrString = None, info: str = "") -> Runner:
        self = LatexRunner(info = info)
        self._lastLogTime = time.time()
        self.process = await asyncio.create_subprocess_shell(command, stdin=PIPE, stdout=PIPE, cwd=workingDirectory)
        self._state = RunnerStates.PREPARING
        self.lines.append(f"I am a LaTeX runner with PID {self.process.pid} (process ID as seen in the task manager) and command\n\t{command}.")
        print(f"Created new LaTeX runner with PID {self.process.pid} (process ID as seen in the task manager) and command\n\t{command}.")
        return self

    async def checkIfProcessTerminated(self):
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self.process.wait(), 1e-6)
        if self.process.returncode is not None:
            return True
        if self._state != RunnerStates.WAITING and \
                self._lastLogTime < time.time() - PROCESS_TIMEOUT and \
                (await self.updateLog() or True) and \
                self._lastLogTime < time.time() - PROCESS_TIMEOUT:
            self.process.kill()
            print("KILLED RUNNER WITH PID", self.process.pid, "after it didn't output anything for", time.time() -self._lastLogTime, "seconds.")
            print('The last lines of its output are:', *self.lines[-10:] , sep='\n\t')
            print("-" * 20)
            return True
        return False


    async def getState(self) -> RunnerStates:
        if self._state != RunnerStates.FINISHED and await self.checkIfProcessTerminated():
            print(f"A runner has finished with returncode {self.process.returncode}! PID: {self.process.pid}. {self.info}")
            if self._state == RunnerStates.PREPARING:
                self.errorState = ErrorStates.NEVER_WAITED
                print("BUT IT NEVER WAITED! IF THIS HAPPENS TO OFTEN I'LL ABORT. PUT \pauseExecution SOMEWHERE IN YOUR DOCUMENT.")
            elif self.process.returncode != 0:
                self.errorState == ErrorStates.RETURN_CODE_NONZERO
            self._state = RunnerStates.FINISHED

        if self._state == RunnerStates.PREPARING:
            for line in await self.updateLog(log=VERBOSE):
                if HALT_LOG in line:
                    self._state = RunnerStates.WAITING
                    print("This runner has switched to the waiting state! PID:", self.process.pid)
                    break
        return self._state
    
    async def continueRun(self):
        
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

    async def stop(self):
        if await self.checkIfProcessTerminated():
            try:
                self.process.kill() 
            except ProcessLookupError:
                pass

        
    async def updateLog(self, timeout: float = 0.05, log: bool = False) -> list:
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
        else:
            lines = (await self.process.stdout.read()).decode('utf-8', errors='replace').splitlines()
        if len(lines) > 0:
            self._lastLogTime = time.time()
            print("\tRead", len(lines), "lines from process", self.process.pid)
            self.lines.extend(lines)
        return lines
#endregion

#region cli (main)

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
            info=f"outputDirectory={outputDirectory}, tempOutputDirectory={tempOutputDirectory}"
        )

    return ProcessWatcher(newRunner)

def clearOldTempDirectories(directory: Path):
    for dir in directory.iterdir():
        if dir.is_dir() and tempFolderRegex.match(dir.name):
            now = datetime.now()
            currentMod = now.hour * 60 + now.minute
            mod = int(dir.name[:2]) * 60 + int(dir.name[3:5])
            if currentMod > OLD_TEMP_DIR_TIMEOUT_MIN and (mod > currentMod or mod < currentMod - OLD_TEMP_DIR_TIMEOUT_MIN):
                try:
                    shutil.rmtree(dir)
                except:
                    pass

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

def mainAsServer(port, texFile: PathOrString = '', output_dir: PathOrString = ''):
    """ Run the server. Blocks until stopped by GET request to f"http://localhost:{port}/stopServer{ROUTE_OBFUSCATION}" """
    from aiohttp import web
    app = web.Application()

    async def handle(request):
        return web.Response(text=await do_execute(texFile=await request.text(), output_dir=output_dir))

    async def handleStopServer(request):
        try:
            raise KeyboardInterrupt("actually interrupted by call to stopServer")
        finally:
            print("Closed by call to \stopServer---")

    app.add_routes([
        web.post(f'/{ROUTE_OBFUSCATION}', handle),
        web.get(f'/stopServer{ROUTE_OBFUSCATION}', handleStopServer)
    ])

    async def startup():
        if texFile != '':
            asyncio.get_event_loop().create_task(
                do_execute(texFile=texFile, output_dir=output_dir) # wrapped in this startup stuff because we only have async from web.run_app
            )

        return app

    web.run_app(startup(), port=port)

def portIsFree(port):
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    res = test_socket.connect_ex(("localhost", port)) != 0
    test_socket.close()
    return res

@click.command()
@click.option("--tex-file", "--file", "--f", "-f", default="")
@click.option("--output-dir", "--output-directory", "--outdir", "--o", "-o", default="out", help="Path for LaTeX output, relative to the tex file. Every LaTeX runner will use a temporary subdirectory and only copy to this directory in the end. Some files will be copied to our temp dir beforehand.")
@click.option("--port", "--p", "-p", default=DEFAULT_PORT, help=f"The port of/for the server (background worker), default = {DEFAULT_PORT}")
@click.option("--start-server-on-demand/--no-server", "--s,--c", "-s/-c", default=True, help="Start a server in a background process if the port is still free. Enabled by default.")
@click.option("--server", is_flag=True, help="Run the server right here. This script will not end by itself.")
@click.option("--stop-server", is_flag=True, help="Stop the already running server by sending a request. Continue as normal after 1 s.")
@click.option("--print-command", "-c", "--c", "--command", "--pc", "-pc", is_flag=True, help="Only show the powershell command and quit.")
@click.option("--verbose", "-v", "--v", is_flag=True, help="Show the complete output of the child processes.")
def main(tex_file, output_dir, port, start_server_on_demand, server, stop_server, print_command, verbose):
    if print_command:
        print(getPowershellCommand(None, output_dir, tex_file))
        return
    global VERBOSE
    VERBOSE = verbose
    portFree = portIsFree(port)
    if stop_server and not portFree:
        try:
            requests.get(f"http://localhost:{port}/stopServer{ROUTE_OBFUSCATION}")
        except requests.exceptions.ConnectionError as e:
            # print("While requesting to stop the following 'error' occurred (as expected?)", e)
            print("Stopped server.")
            pass
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
            mainAsServer(port=port, texFile=tex_file, output_dir=output_dir)
        else:
            print("COULDN'T START THE SERVER, BECAUSE THE PORT IS NOT FREE. IS THERE ANOTHER SERVER RUNNING? KILL IT BY RUNNING THIS AGAIN WITH THE --stop-server FLAG.")
        return
    if tex_file != '' and start_server_on_demand and portFree:
        # command_args = [sys.executable, '"'+__file__+'"', f'--p {port}', f'--o {output_dir}', '--server', f'--f {tex_file}' ]
        # pid = os.spawnl(os.P_NOWAIT, *command_args)
        command_args = [
            sys.executable, __file__, '--port', str(port), '--o', str(output_dir), '--server', '--f', str(tex_file)
        ] # single dash arguments are interpreted as options to python (sys.executable)
        pid = subprocess.Popen(command_args, creationflags=DETACHED_PROCESS, close_fds=True).pid
        print("STARTED SERVER (BACKGROUND WORKER) WITH PID", pid, "using command ", *command_args)
        print("STOP IT BY CALLING THIS AGAIN WITH THE --stop-server FLAG.")
        print("Your compilation will be done, but you won't see the logs here.")
    if tex_file != '' and not portFree:
        print("Sending request to server (background worker)")
        sendData = str(tex_file).encode('utf8')
        requestResult = requests.post(f"http://localhost:{port}/{ROUTE_OBFUSCATION}", data=sendData)
        content = requestResult.content
        text = content.decode('utf8')
        print(text)
        print("Server finished.")



if __name__ == '__main__':
    main()