from abc import ABC, ABCMeta, abstractmethod
import asyncio
from asyncio.subprocess import PIPE, Process
import contextlib
from enum import Enum
import asyncio.subprocess as sp
from pathlib import Path
from typing import Generic, TextIO, TypeVar

from matplotlib.style import available
    
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
    def __init__(self, command, T: type, workingDirectory: str = None) -> None:
        """ T must be a subclass of Runner """
        self.runners: list[Runner] = []
        self.oldRunners: list[Runner] = []
        self.command = command
        self.workingDirectory = workingDirectory
        self.minNumberAvailable = 2
        self.watchSleepTime = 0.6
        self.watchTask: asyncio.Task = None
        self.T = T

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
            print("Creating a new runner of type", self.T.__name__)
            self.runners.append(await self.T.newRunner(self.command, self.workingDirectory))
            
    async def watch(self):
        print("WATCHER STARTED")
        while True:
            await self.refreshState()
            await asyncio.sleep(self.watchSleepTime)

    async def runWatcher(self):
        if self.watchTask is None:
            self.watchTask = asyncio.get_running_loop().create_task(self.watch())
    
    async def stopWatcher(self):
        if self.watchTask is None:
            return
        print("Stopping the Watcher ...", end='', flush=True)
        self.watchTask.cancel()
        while not self.watchTask.cancelled():
            await asyncio.sleep(0.1)
        print("WATCHER STOPPED")
        self.watchTask = None
        print("done")

    async def execute(self, waitForCompletion: bool = False):
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
            while execute_runner not in self.oldRunners and i < 100: # let the watcher do the state checking
                await asyncio.sleep(0.6)
                i += 1
            if i >= 100:
                return "ABORTED AFTER 60 SECONDS" +     "\n".join(execute_runner.lines)
        return "\n".join(execute_runner.lines) 


class LatexRunner(Runner):

    def __init__(self) -> None:
        """ Call the async static method newRunner instead """
        super().__init__()
        self.process: Process = None
        self._state: RunnerStates = None

    @staticmethod
    async def newRunner(command: str = "lualatex test", workingDirectory: str = None) -> Runner:
        self = LatexRunner()
        self.process = await asyncio.create_subprocess_shell(command, stdin=PIPE, stdout=PIPE, cwd=workingDirectory)
        self._state = RunnerStates.PREPARING
        print("Created new LaTeX runner with PID", self.process.pid, "(process ID as seen in the task manager)")
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
            for line in await self.readlines_alreadyWritten():
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
                line = str(
                    await asyncio.wait_for(
                        self.process.stdout.readline(),
                        timeout = timeout
                    )
                )
                if log:
                    print('\t', line)
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

def mainAsServer(command, workingDirectory):
    from aiohttp import web

    watcher: ProcessWatcher = None
    async def handle(request):
        nonlocal watcher
        name = request.match_info.get('name', "Anonymous")
        print(f"Got request to /{name}")

        if watcher is None:
            watcher = ProcessWatcher(command, workingDirectory=workingDirectory, T = LatexRunner)
        
            
        return web.Response(text=
            await watcher.execute(waitForCompletion=True)
        )

    app = web.Application()
    app.add_routes([web.get('/', handle),
                    web.get('/{name}', handle)])

    web.run_app(app)

def mainAsClient():
    from requests import get
    print(get(f"http://localhost:{port}/").content)#{texFile.name}

texFile = Path("B:\\LaTeX-Privat\\Motivationsschreiben\\Motivationsschreiben.tex")
if __name__ == '__main__':
    port = 8080
    command = f"lualatex {texFile}"
    try:
        mainAsServer(command, str(texFile.parent))
    except OSError:
        print(f"There is already a server running on port {port},  so I sent a request to it.")
        mainAsClient()