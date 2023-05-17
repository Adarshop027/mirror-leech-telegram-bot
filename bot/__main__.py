#!/usr/bin/env python3
from signal import signal, SIGINT
from aiofiles.os import path as aiopath, remove as aioremove
from aiofiles import open as aiopen
from os import execl as osexecl
from psutil import disk_usage, cpu_percent, swap_memory, cpu_count, virtual_memory, net_io_counters, boot_time
from time import time
from sys import executable
from pyrogram.handlers import MessageHandler
from pyrogram.filters import command
from asyncio import create_subprocess_exec, gather

from bot import bot, botStartTime, LOGGER, Interval, DATABASE_URL, QbInterval, INCOMPLETE_TASK_NOTIFIER, scheduler
from .helper.ext_utils.fs_utils import start_cleanup, clean_all, exit_clean_up
from .helper.ext_utils.bot_utils import get_readable_file_size, get_readable_time, cmd_exec, sync_to_async
from .helper.ext_utils.db_handler import DbManger
from .helper.telegram_helper.bot_commands import BotCommands
from .helper.telegram_helper.message_utils import sendMessage, editMessage, sendFile, auto_delete_message
from .helper.telegram_helper.filters import CustomFilters
from .helper.telegram_helper.button_build import ButtonMaker
from bot.helper.listeners.aria2_listener import start_aria2_listener
from .modules import authorize, clone, gd_count, gd_delete, gd_list, cancel_mirror, mirror_leech, status, torrent_search, torrent_select, ytdlp, rss, shell, eval, users_settings, bot_settings

start_aria2_listener()


async def stats(client, message):
    if await aiopath.exists('.git'):
        last_commit = await cmd_exec("git log -1 --date=short --pretty=format:'%cd <b>From</b> %cr'", True)
        last_commit = last_commit[0]
    else:
        last_commit = 'No UPSTREAM_REPO'
    total, used, free, disk = disk_usage('/')
    swap = swap_memory()
    memory = virtual_memory()
    stats = f'<b>Commit Date:</b> {last_commit}\n\n'\
            f'<b>Bot Uptime:</b> {get_readable_time(time() - botStartTime)}\n'\
            f'<b>OS Uptime:</b> {get_readable_time(time() - boot_time())}\n\n'\
            f'<b>Total Disk Space:</b> {get_readable_file_size(total)}\n'\
            f'<b>Used:</b> {get_readable_file_size(used)} | <b>Free:</b> {get_readable_file_size(free)}\n\n'\
            f'<b>Upload:</b> {get_readable_file_size(net_io_counters().bytes_sent)}\n'\
            f'<b>Download:</b> {get_readable_file_size(net_io_counters().bytes_recv)}\n\n'\
            f'<b>CPU:</b> {cpu_percent(interval=0.5)}%\n'\
            f'<b>RAM:</b> {memory.percent}%\n'\
            f'<b>DISK:</b> {disk}%\n\n'\
            f'<b>Physical Cores:</b> {cpu_count(logical=False)}\n'\
            f'<b>Total Cores:</b> {cpu_count(logical=True)}\n\n'\
            f'<b>SWAP:</b> {get_readable_file_size(swap.total)} | <b>Used:</b> {swap.percent}%\n'\
            f'<b>Memory Total:</b> {get_readable_file_size(memory.total)}\n'\
            f'<b>Memory Free:</b> {get_readable_file_size(memory.available)}\n'\
            f'<b>Memory Used:</b> {get_readable_file_size(memory.used)}\n'
    msg = await sendMessage(message, stats)
    await auto_delete_message(message, msg)


start_auth ='''
<b>Bot is Activate.</b>
This bot can mirror your [Links | Files | Torrents] to Google Drive or any Rclone Cloud or to Telegram.

<b>Warning!</b>
Cloud and Dump are public, everyone can view and download it. Therefore, don't mirror or leech files that are confidential or personal data!

Type <b>/help</b> to get more information.
'''
async def start(client, message):
    buttons = ButtonMaker()
    buttons.ubutton("Cloud", "https://mirrorbotdrive.eu.org/0:/")
    buttons.ubutton("Dump", "http://t.me/leechsdump")
    reply_markup = buttons.build_menu(2)
    msg = await sendMessage(message, start_string, reply_markup)
    await auto_delete_message(message, msg)
    

async def restart(client, message):
    restart_message = await sendMessage(message, "Restarting...")
    if scheduler.running:
        scheduler.shutdown(wait=False)
    for interval in [QbInterval, Interval]:
        if interval:
            interval[0].cancel()
    await sync_to_async(clean_all)
    proc1 = await create_subprocess_exec('pkill', '-9', '-f', 'gunicorn|aria2c|qbittorrent-nox|ffmpeg|rclone')
    proc2 = await create_subprocess_exec('python3', 'update.py')
    await gather(proc1.wait(), proc2.wait())
    async with aiopen(".restartmsg", "w") as f:
        await f.write(f"{restart_message.chat.id}\n{restart_message.id}\n")
    osexecl(executable, executable, "-m", "bot")


async def ping(client, message):
    start_time = int(round(time() * 1000))
    reply = await sendMessage(message, "Checking ...")
    end_time = int(round(time() * 1000))
    msg = await editMessage(reply, f'<b>Latency:</b> {end_time - start_time}ms')
    await auto_delete_message(message, msg)


async def log(client, message):
    msg = await sendFile(message, 'log.txt')
    await auto_delete_message(message, msg)


help_string = '''
<b>INFORMATION</b>
<b>m</b> or <b>mirror</b>: Download and upload to Cloud Storage.
<b>l</b> or <b>leech</b>: Download and upload to Telegram.
q or qb: For magnet link or torrent file.
<b>z</b> or <b>zip</b>: Archive file before upload.
<b>uz</b> or <b>unzip</b>: Extract file before upload.
<b>y</b> or <b>ytdl</b>p: For yt-dlp links.

<b>FOR DIRECT DOWNLOAD LINK OR FILE</b>
[ / + z/uz + m/l ] or [ / + zip/unzip + mirror/leech ]
Ex. <code>/zm</code> [or] <code>/zipmirror</code>:
Download and archive file before upload to Cloud Storage.

<b>FOR MAGNET LINK OR TORRENT FILE</b>
[ / + q + z/uz + l/m ] or [ qb + zip/unzip + leech/mirror ]
Ex. <code>/qzm</code> [or] <code>/qbzipmirror</code>:
Download torrent and archive file before upload to Cloud Storage.

<b>FOR YT-DLP LINKS</b>
[ / + y + z + l ] or [ / + ytdl + zip + leech ]
Ex. <code>/yzl</code> [or] <code>ytdlzipleech</code>:
Download and archive file before upload to Telegram.

<b>NOTES</b>
• <b>uz</b> or <b>unzip</b> only for archive files (zip, RAR, etc.) and not work for <b>y</b> or <b>ytdl</b>.
• After <b>y</b> or <b>ytdl</b> no need <b>m</b> or <b>mirror</b> if you want upload to Cloud Storage.

<b>MORE</b>
Just send one of several existing command when you type "<b>/</b>" (slash), to see details of the command.
'''
async def bot_help(client, message):
    buttons = ButtonMaker()
    buttons.ubutton("Source", "https://github.com/anasty17/mirror-leech-telegram-bot")
    buttons.ubutton("Feedback", "http://t.me/ilhamtgbot")
    reply_markup = buttons.build_menu(2)
    msg = await sendMessage(message, help_string, reply_markup)
    await auto_delete_message(message, msg)


async def restart_notification():
    if await aiopath.isfile(".restartmsg"):
        with open(".restartmsg") as f:
            chat_id, msg_id = map(int, f)
    else:
        chat_id, msg_id = 0, 0

    async def send_incompelete_task_message(cid, msg):
        try:
            if msg.startswith('Restarted Successfully!'):
                await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=msg)
                await aioremove(".restartmsg")
            else:
                await bot.send_message(chat_id=cid, text=msg, disable_web_page_preview=True,
                                       disable_notification=True)
        except Exception as e:
            LOGGER.error(e)

    if INCOMPLETE_TASK_NOTIFIER and DATABASE_URL:
        if notifier_dict := await DbManger().get_incomplete_tasks():
            for cid, data in notifier_dict.items():
                msg = 'Restarted Successfully!' if cid == chat_id else 'Bot Restarted!'
                for tag, links in data.items():
                    msg += f"\n\n{tag}: "
                    for index, link in enumerate(links, start=1):
                        msg += f" <a href='{link}'>{index}</a> |"
                        if len(msg.encode()) > 4000:
                            await send_incompelete_task_message(cid, msg)
                            msg = ''
                if msg:
                    await send_incompelete_task_message(cid, msg)

    if await aiopath.isfile(".restartmsg"):
        try:
            await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text='Restarted Successfully!')
        except:
            pass
        await aioremove(".restartmsg")


async def main():
    await gather(start_cleanup(), torrent_search.initiate_search_tools(), restart_notification())
    bot.add_handler(MessageHandler(start, filters=command(BotCommands.StartCommand)))
    bot.add_handler(MessageHandler(log, filters=command(
        BotCommands.LogCommand) & CustomFilters.owner))
    bot.add_handler(MessageHandler(restart, filters=command(
        BotCommands.RestartCommand) & CustomFilters.owner))
    bot.add_handler(MessageHandler(ping, filters=command(
        BotCommands.PingCommand)))
    bot.add_handler(MessageHandler(bot_help, filters=command(
        BotCommands.HelpCommand)))
    bot.add_handler(MessageHandler(stats, filters=command(
        BotCommands.StatsCommand) & CustomFilters.sudo))
    LOGGER.info("Bot Started!")
    signal(SIGINT, exit_clean_up)

bot.loop.run_until_complete(main())
bot.loop.run_forever()