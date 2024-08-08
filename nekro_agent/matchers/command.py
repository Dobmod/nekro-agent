from typing import List, Tuple, Union

from miose_toolkit_common import Env
from nonebot import on_command
from nonebot.adapters import Bot, Message
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageEvent
from nonebot.matcher import Matcher
from nonebot.params import CommandArg

from nekro_agent.core.config import config, reload_config
from nekro_agent.core.logger import logger
from nekro_agent.models.db_chat_message import DBChatMessage
from nekro_agent.schemas.chat_message import ChatType
from nekro_agent.services.chat import chat_service
from nekro_agent.services.sandbox.executor import limited_run_code
from nekro_agent.tools.onebot_util import gen_chat_text, get_chat_info, get_user_name


async def command_guard(
    event: Union[MessageEvent, GroupMessageEvent],
    bot: Bot,
    arg: Message,
    matcher: Matcher,
) -> Tuple[str, str, str, ChatType]:
    username = await get_user_name(event=event, bot=bot, user_id=event.get_user_id())
    # 判断是否是禁止使用的用户
    if event.get_user_id() not in config.SUPER_USERS:
        logger.warning(f"用户 {username} 不在允许用户中")
        await matcher.finish(f"用户 [{event.get_user_id()}]{username} 不在允许用户中")

    cmd_content: str = arg.extract_plain_text()
    chat_key, chat_type = await get_chat_info(event=event)
    return username, cmd_content, chat_key, chat_type


@on_command("reset", priority=5, block=True).handle()
async def _(matcher: Matcher, event: MessageEvent, bot: Bot, arg: Message = CommandArg()):
    username, cmd_content, chat_key, chat_type = await command_guard(event, bot, arg, matcher)

    target_chat_key: str = cmd_content or chat_key
    if not target_chat_key:
        await matcher.finish(message="请指定要清空聊天记录的会话")
    msgs = DBChatMessage.filter(conditions={DBChatMessage.chat_key: target_chat_key})
    msg_cnt = len(msgs)

    for msg in msgs:
        msg.delete()
    await matcher.finish(message=f"已清空 {msg_cnt} 条 {target_chat_key} 的聊天记录")


@on_command("exec", priority=5, block=True).handle()
async def _(matcher: Matcher, event: MessageEvent, bot: Bot, arg: Message = CommandArg()):
    username, cmd_content, chat_key, chat_type = await command_guard(event, bot, arg, matcher)

    result: str = await limited_run_code(cmd_content, from_chat_key=chat_key)

    if result:
        await matcher.finish(result)


@on_command("config_show", priority=5, block=True).handle()
async def _(matcher: Matcher, event: MessageEvent, bot: Bot, arg: Message = CommandArg()):
    username, cmd_content, chat_key, chat_type = await command_guard(event, bot, arg, matcher)

    if not cmd_content:
        modifiable_config_key: List[str] = []
        for _key, _value in config.dump_config_template().items():
            if isinstance(_value, (int, float, bool, str)):
                modifiable_config_key.append(_key)
        sep = "\n"
        await matcher.finish(message=f"当前支持动态修改配置：\n{sep.join([f'- {k}' for k in modifiable_config_key])}")
    else:
        if config.dump_config_template().get(cmd_content):
            await matcher.finish(message=f"当前配置：\n{cmd_content}={getattr(config, cmd_content)}")
        else:
            await matcher.finish(message=f"未知配置 `{cmd_content}`")


@on_command("config_set", priority=5, block=True).handle()
async def _(matcher: Matcher, event: MessageEvent, bot: Bot, arg: Message = CommandArg()):
    username, cmd_content, chat_key, chat_type = await command_guard(event, bot, arg, matcher)

    try:
        key, value = cmd_content.strip().split("=", 1)
    except ValueError:
        await matcher.finish(message="参数错误，请使用 `config_set key=value` 的格式")

    if config.dump_config_template().get(key):
        _c_type = type(getattr(config, key))
        _c_value = getattr(config, key)
        if isinstance(_c_value, (int, float)):
            setattr(config, key, _c_type(value))
        elif isinstance(_c_value, bool):
            if value.lower() in ["true", "1", "yes"]:
                setattr(config, key, True)
            elif value.lower() in ["false", "0", "no"]:
                setattr(config, key, False)
            else:
                await matcher.finish(message=f"布尔值只能是 `true` 或 `false`，请检查 `{key}` 的值")
        elif isinstance(_c_value, str):
            setattr(config, key, _c_type(value))
        else:
            await matcher.finish(message=f"不支持动态修改的配置类型 `{_c_type}`")
        await matcher.finish(message=f"已设置 `{key}` 的值为 `{value}`")


@on_command("config_reload", priority=5, block=True).handle()
async def _(matcher: Matcher, event: MessageEvent, bot: Bot, arg: Message = CommandArg()):
    username, cmd_content, chat_key, chat_type = await command_guard(event, bot, arg, matcher)

    await matcher.finish(message="功能未实现")
    try:
        config.dump_config(envs=[Env.Default.value])
    except Exception as e:
        await matcher.finish(message=f"保存配置失败：{e}")
    else:
        await matcher.finish(message="已保存配置")


@on_command("config_save", priority=5, block=True).handle()
async def _(matcher: Matcher, event: MessageEvent, bot: Bot, arg: Message = CommandArg()):
    username, cmd_content, chat_key, chat_type = await command_guard(event, bot, arg, matcher)

    reload_config()
    await matcher.finish(message="重载配置成功")
