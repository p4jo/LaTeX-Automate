from abc import ABCMeta, abstractmethod
import asyncio
from asyncio.subprocess import PIPE, Process
import contextlib
from datetime import datetime
from enum import Enum
from os import PathLike
from pathlib import Path
from typing import Awaitable, Callable, Dict
import click
import requests

    
class RunnerStates(Enum):
    PREPARING = 0
    WAITING = 1
    RUNNING = 2
    FINISHED = 3

class Runner(metaclass = ABCMeta):
    def __init__(self) -> None:
        self.lines: list[str] = []

    @abstractmethod
    async def getState(self)->RunnerStates:
        pass
    @abstractmethod
    async def continueRun(self):
        pass

    @staticmethod
    @abstractmethod
    async def newRunner():
        pass

class ProcessWatcher():
    minNumberAvailable = 2
    _watchSleepTime = 0.6

    def __init__(self, newRunnerCallback: Callable[..., Awaitable[Runner]]) -> None:
        self.newRunner = newRunnerCallback

        self.runners: list[Runner] = []
        self.oldRunners: list[Runner] = []
        self.watchTask: asyncio.Task = None
        

    async def refreshState(self):
        availableRunners: list[Runner] = []

        for runner in self.runners:
            state = await runner.getState()
            if state == RunnerStates.FINISHED or state == RunnerStates.RUNNING:
                self.oldRunners.append(runner)
            if state == RunnerStates.WAITING or state == RunnerStates.PREPARING:
                availableRunners.append(runner)
        
        self.runners = availableRunners
        
        for _ in range(len(self.runners), self.minNumberAvailable):
            print(f"Only {len(self.runners)}/{self.minNumberAvailable} runners available, starting a new runner ") #of type", self.T.__name__)
            self.runners.append(await self.newRunner())
            
    async def watch(self):
        print("WATCHER STARTED")
        while True:
            await self.refreshState()
            await asyncio.sleep(self._watchSleepTime)

    async def runWatcher(self):
        if self.watchTask is None:
            self.watchTask = asyncio.get_running_loop().create_task(self.watch())
    
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

    _executionTimeout = 50
    async def execute(self, waitForCompletion: bool = False):
        output: str = ""
        await self.stopWatcher() # the watcher might currently access the stdout.readline() method. Python throws a RuntimeError when we then also access it.
        await self.refreshState()

        execute_runner = self.runners[0]
        for runner in self.runners:
            if await runner.getState() == RunnerStates.WAITING:
               execute_runner = runner
               break

        await execute_runner.continueRun()
        await self.runWatcher()
        if waitForCompletion:
            i = 0
            while execute_runner not in self.oldRunners and i < self._executionTimeout/self._watchSleepTime: # let the watcher do the state checking
                await asyncio.sleep(self._watchSleepTime)
                i += 1
            if i >= self._executionTimeout/self._watchSleepTime:
                execute_runner.lines.insert(0, f"ABORTED AFTER {self._executionTimeout} SECONDS")
                print(f"ABORTED AFTER {self._executionTimeout} SECONDS. PID", execute_runner.process.pid)
        if isinstance(execute_runner, LatexRunner):
            await execute_runner.readlines_alreadyWritten()
        print("Execution finished. PID:", execute_runner.process.pid)
        return "".join(execute_runner.lines) 


class LatexRunner(Runner):

    def __init__(self, outputDirectory, currentOutputDirectory) -> None:
        """ Call the async static method newRunner instead """
        super().__init__()
        self.process: Process = None
        self._state: RunnerStates = None
        self.outputDirectory = outputDirectory
        self.currentOutputDirectory = currentOutputDirectory

    @staticmethod
    async def newRunner(command: str = "lualatex test", workingDirectory: str = None, outputDirectory: PathLike = None, tempOutputDirectory: PathLike = None) -> Runner:
        self = LatexRunner(outputDirectory=outputDirectory, currentOutputDirectory=tempOutputDirectory)
        self.process = await asyncio.create_subprocess_shell(command, stdin=PIPE, stdout=PIPE, cwd=workingDirectory)
        self._state = RunnerStates.PREPARING
        print("Created new LaTeX runner with PID", self.process.pid, f"(process ID as seen in the task manager) and command {command}")
        return self

    async def checkIfProcessTerminated(self):
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(self.process.wait(), 1e-6)
        return self.process.returncode is not None


    async def getState(self) -> RunnerStates:
        if await self.checkIfProcessTerminated():
            print("A runner has finished! PID: ", self.process.pid)
            self._state = RunnerStates.FINISHED
        if self._state == RunnerStates.PREPARING:
            for line in await self.readlines_alreadyWritten(log=True):
                if "\\pauseExecution" in line:
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
            # actually wait for new output
            # await readlines_alreadyWritten(self.process, timeout=1, log=True) # doesn't stop when process is done...
        # await self.getState()

        
    async def readlines_alreadyWritten(self, timeout: float = 0.05, log: bool = False) -> list:
        lines: list[str] = []
        while True:
            try:
                line = (
                    await asyncio.wait_for(
                        self.process.stdout.readline(),
                        timeout = timeout
                    )
                ).decode("utf-8") 
                if log:
                    print('\t\t', line)
                lines.append(line)
            except asyncio.TimeoutError:
                # print("Buffered latex log output exceeded! PID:", process.pid)
                break
        print("\tRead", len(lines), "lines from process", self.process.pid)
        self.lines.extend(lines)
        return lines


# async def main():     
#     while True:
#         input("Press Enter to start a run")
#         await watcher.execute()

# if __name__ == '__main__':
#     asyncio.run(main())

def newWatcher(texFile: PathLike, output_dir):
            if texFile is None or texFile == "":
                return None
            texFile = Path(texFile)
            if not texFile.is_file():
                return None
            if output_dir is None:
                output_dir = "out"
            outputDirectory = texFile.parent / output_dir
            tempOutputDirectory = outputDirectory / datetime.now().strftime("%H-%M-%S")
            async def newRunner():
                return await LatexRunner.newRunner(
                    command = f"lualatex {texFile.name} -recorder -file-line-error -halt-on-error -synctex=1 --output-directory={tempOutputDirectory}",
                    workingDirectory=texFile.parent,    
                    outputDirectory=outputDirectory,
                    tempOutputDirectory= tempOutputDirectory 
                )

            return ProcessWatcher(newRunner)

watchers: Dict[str, ProcessWatcher] = {}
async def do_execute(texFile, output_dir = None):
    if texFile is None or texFile == '':
        print("No file path provided!")
        return
    global watchers
    if texFile not in watchers:
        watchers[texFile] = newWatcher(texFile=texFile, output_dir=output_dir)
    watcher = watchers[texFile]
    if watcher is None:
        print("potential Error when creating watcher.")
        return None
    return await watcher.execute(waitForCompletion=True)

def mainAsServer(port, texFile: PathLike = None, output_dir=None):
    from aiohttp import web

    async def handle(request):
        return web.Response(text=await do_execute(texFile=await request.text(), output_dir=output_dir))

    async def startup():
        if texFile is not None:
            await do_execute(texFile=texFile, output_dir=output_dir) # wrapped in this startup stuff because we only have async from web.run_app

        app = web.Application()
        app.add_routes([web.post('/', handle)])
        return app

    web.run_app(startup(), port=port)

@click.command()
@click.option("--texFile", "-f", default="")
@click.option("--output-dir", "--outdir", "-o", default="", help="relative to the tex file")
@click.option("--port", "-p", default=8080)
def main(texfile, output_dir, port):        
    try:
        mainAsServer(port=port, texFile=texfile, output_dir=output_dir)
    except OSError:
        print(f"There is already a server running on port {port}, so I sent a request to it.")
        print(requests.post(f"http://localhost:{port}/", data=str(texfile)).content.decode('utf8'))

if __name__ == '__main__':
    main()