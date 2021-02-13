
from __future__ import annotations

from typing import Final

from pymap.config import IMAPConfig
from pymap.interfaces.filter import FilterSetInterface

from .command import Command, HaveSpaceCommand, PutScriptCommand, \
    ListScriptsCommand, SetActiveCommand, GetScriptCommand, \
    DeleteScriptCommand, RenameScriptCommand, CheckScriptCommand
from .response import Condition, Response, GetScriptResponse, \
    ListScriptsResponse
from .. import SieveParseError

__all__ = ['FilterState']


class FilterState:

    def __init__(self, filter_set: FilterSetInterface[bytes],
                 owner: bytes, config: IMAPConfig) -> None:
        super().__init__()
        self.filter_set: Final = filter_set
        self.owner: Final = owner
        self.config: Final = config

    async def _do_have_space(self, cmd: HaveSpaceCommand) -> Response:
        max_len = self.config.max_filter_len
        if max_len is None or cmd.size <= max_len:
            return Response(Condition.OK)
        else:
            return Response(Condition.NO, code=b'QUOTA/MAXSIZE')

    async def _do_put_script(self, cmd: PutScriptCommand) -> Response:
        max_len = self.config.max_filter_len
        if max_len is None or len(cmd.script_data) <= max_len:
            await self.filter_set.put(cmd.script_name, cmd.script_data)
            return Response(Condition.OK)
        else:
            return Response(Condition.NO, code=b'QUOTA/MAXSIZE')

    async def _do_list_scripts(self) -> Response:
        active, names = await self.filter_set.get_all()
        return ListScriptsResponse(active, names)

    async def _do_set_active(self, cmd: SetActiveCommand) -> Response:
        if cmd.script_name is None:
            await self.filter_set.clear_active()
        else:
            try:
                await self.filter_set.set_active(cmd.script_name)
            except KeyError:
                return Response(Condition.NO, code=b'NONEXISTENT')
        return Response(Condition.OK)

    async def _do_get_script(self, cmd: GetScriptCommand) -> Response:
        try:
            script_data = await self.filter_set.get(cmd.script_name)
        except KeyError:
            return Response(Condition.NO, code=b'NONEXISTENT')
        return GetScriptResponse(script_data)

    async def _do_delete_script(self, cmd: DeleteScriptCommand) -> Response:
        try:
            await self.filter_set.delete(cmd.script_name)
        except KeyError:
            return Response(Condition.NO, code=b'NONEXISTENT')
        except ValueError:
            return Response(Condition.NO, code=b'ACTIVE')
        else:
            return Response(Condition.OK)

    async def _do_rename_script(self, cmd: RenameScriptCommand) -> Response:
        try:
            await self.filter_set.rename(cmd.old_script_name,
                                         cmd.new_script_name)
        except KeyError as exc:
            if exc.args == (cmd.old_script_name, ):
                return Response(Condition.NO, code=b'NONEXISTENT')
            elif exc.args == (cmd.new_script_name, ):
                return Response(Condition.NO, code=b'ALREADYEXISTS')
            else:
                return Response(Condition.NO)
        else:
            return Response(Condition.OK)

    async def _do_check_script(self, cmd: CheckScriptCommand) -> Response:
        try:
            await self.filter_set.compiler.compile(cmd.script_data)
        except SieveParseError as exc:
            return Response(Condition.NO, text=str(exc))
        else:
            return Response(Condition.OK)

    async def run(self, cmd: Command) -> Response:
        try:
            if isinstance(cmd, HaveSpaceCommand):
                return await self._do_have_space(cmd)
            elif isinstance(cmd, PutScriptCommand):
                return await self._do_put_script(cmd)
            elif isinstance(cmd, ListScriptsCommand):
                return await self._do_list_scripts()
            elif isinstance(cmd, SetActiveCommand):
                return await self._do_set_active(cmd)
            elif isinstance(cmd, GetScriptCommand):
                return await self._do_get_script(cmd)
            elif isinstance(cmd, DeleteScriptCommand):
                return await self._do_delete_script(cmd)
            elif isinstance(cmd, RenameScriptCommand):
                return await self._do_rename_script(cmd)
            elif isinstance(cmd, CheckScriptCommand):
                return await self._do_check_script(cmd)
            else:
                return Response(Condition.NO, text='Bad command.')
        except NotImplementedError:
            return Response(Condition.NO, text='Action not supported.')
