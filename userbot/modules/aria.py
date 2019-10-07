# Copyright (C) 2019 The Raphielscape Company LLC.
#
# Licensed under the Raphielscape Public License, Version 1.c (the "License");
# you may not use this file except in compliance with the License.

import aria2p
import asyncio
import math
from os import system
import io
from userbot import LOGS, CMD_HELP, TEMP_DOWNLOAD_DIRECTORY
from userbot.events import register
from requests import get

aria2 = None


@register(outgoing=True, pattern="^.aria_start$")
async def aria_kickstart(event):
    # Get best trackers for improved download speeds, thanks K-E-N-W-A-Y.
    LOGS.info("Fetching trackers for local aria2 server....")
    trackers_list = get(
        'https://raw.githubusercontent.com/ngosang/trackerslist/master/trackers_all.txt'
    ).text.replace('\n\n', ',')
    trackers = f"[{trackers_list}]"
    LOGS.info(f"Current trackers list: {trackers}")

    # Command for starting aria2 local server.
    aria_start_shell = f"aria2c \
    --enable-rpc=true \
    --rpc-listen-all=false \
    --rpc-listen-port 6800 \
    --max-connection-per-server=10 \
    --rpc-max-request-size=1024M \
    --seed-ratio=100.0 \
    --seed-time=1 \
    --max-upload-limit=5K \
    --max-concurrent-downloads=5 \
    --min-split-size=10M \
    --follow-torrent=mem \
    --split=10 \
    --bt-tracker={trackers} \
    --dir='{TEMP_DOWNLOAD_DIRECTORY}' \
    --allow-overwrite=true"
    
    # Since the command is too long to exec,
    # let's split it into a list of args.
    aria_start_cmd = aria_start_shell.split()

    try:
        process = await asyncio.create_subprocess_exec(
            *aria_start_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await process.communicate()
        LOGS.info(stdout)
        LOGS.info(stderr)
    except FileNotFoundError:
        await event.edit("`Install aria2c first, KThxBye.`")
        return
    global aria2
    aria2 = aria2p.API(
        aria2p.Client(host="http://localhost", port=6800, secret=""))
    await event.edit(f"`Local aria2 server online !!`\
    \nPID: {process.pid}")


@register(outgoing=True, pattern="^.magnet(?: |$)(.*)")
async def magnet_download(event):
    if not aria2:
        await event.edit(
            "`Local aria2 server is offline, use .aria_start to kick start the service.`"
        )
        return
    magnet_uri = event.pattern_match.group(1)
    # Add Magnet URI Into Queue
    try:
        download = aria2.add_magnet(magnet_uri)
    except Exception as e:
        LOGS.info(str(e))
        await event.edit("Error:\n`" + str(e) + "`")
        return
    gid = download.gid
    file = aria2.get_download(gid)
    await event.edit("`Fetching metadata from magnet link, please wait.`")
    final_gid = file.followed_by_ids[0]
    LOGS.info("Changing GID " + gid + " to " + final_gid)
    await check_progress_for_dl(final_gid, event)


@register(outgoing=True, pattern="^.torrent(?: |$)(.*)")
async def torrent_download(event):
    if not aria2:
        await event.edit(
            "`Local aria2 server is offline, use .aria_start to kick start the service.`"
        )
        return
    torrent_file_path = event.pattern_match.group(1)
    # Add Torrent Into Queue
    try:
        download = aria2.add_torrent(torrent_file_path,
                                     uris=None,
                                     options=None,
                                     position=None)
    except Exception as e:
        LOGS.info(str(e))
        await event.edit("Error:\n`" + str(e) + "`")
        return
    gid = download.gid
    await check_progress_for_dl(gid, event)


@register(outgoing=True, pattern="^.aria_dl(?: |$)(.*)")
async def magnet_download(event):
    uri = [event.pattern_match.group(1)]
    try:  # Add URL Into Queue
        download = aria2.add_uris(uri, options=None, position=None)
    except Exception as e:
        LOGS.info(str(e))
        await event.edit("Error :\n`{}`".format(str(e)))
        return
    gid = download.gid
    await check_progress_for_dl(gid, event)


@register(outgoing=True, pattern="^.aria_clr$")
async def remove_all(event):
    try:
        removed = aria2.remove_all(force=True)
        aria2.purge_all()
    except:
        pass
    if not removed:  # If API returns False Try to Remove Through System Call.
        system("aria2p remove-all")
    await event.edit("`Successfully cleared the download queue.`")


@register(outgoing=True, pattern="^.aria_pause$")
async def pause_all(event):
    # Pause ALL Currently Running Downloads.
    paused = aria2.pause_all(force=True)
    await event.edit(f"`Successfully paused on-going downloads.`\
    \nOutput: {str(paused)}")


@register(outgoing=True, pattern="^.aria_resume$")
async def resume_all(event):
    resumed = aria2.resume_all()
    await event.edit(f"`Resumed current download queue on aria2 local server.`\
    \nOutput: {str(resumed)}")


@register(outgoing=True, pattern="^.aria_stats$")
async def show_all(event):
    output = "output.txt"
    if not aria2:
        await event.edit(
            "`No ongoing downloads, coz local aria2 server is not running.`\
        \n`Spin up a new instance of the aria2 server using .startaria`")
        return
    downloads = aria2.get_downloads()
    msg = ""
    for download in downloads:
        msg = msg + "File: `" + str(download.name) + "`\nSpeed: " + str(
            download.download_speed_string()) + "\nProgress: " + str(
                download.progress_string()) + "\nTotal Size: " + str(
                    download.total_length_string()) + "\nStatus: " + str(
                        download.status) + "\nETA:  " + str(
                            download.eta_string()) + "\n\n"
    if len(msg) <= 4096:
        await event.edit("`On-going Downloads: `\n" + msg)
        await asyncio.sleep(5)
        await event.delete()
    else:
        with io.BytesIO(str.encode(msg)) as out_file:
            out_file.name = "aria_stats.txt"
        await event.client.send_file(
            event.chat_id,
            out_file,
            force_document=True,
            allow_cache=False,
            caption="`Here's my HUGE download queue.`",
        )


async def check_progress_for_dl(gid, event):
    previous_message = None
    file = aria2.get_download(gid)
    while not file.is_complete:
        file = aria2.get_download(gid)
        try:
            if not file.error_message:
                percentage = file.progress()
                progress_str = "[{0}{1}] {2}%\n".format(
                    ''.join(["▰" for i in range(math.floor(percentage / 10))]),
                    ''.join([
                        "▱" for i in range(10 - math.floor(percentage / 10))
                    ]), round(percentage, 2))
                msg = f"\nName: `{file.name}`"
                msg += f"\n🔽: {file.download_speed_string()} / 🔼: {file.upload_speed_string()}"
                msg += f"\n{progress_str}"
                msg += f"\nSize: {file.total_length_string()}"
                msg += f"\nStatus: {file.status}"
                msg += f"\nETA: {file.eta_string()}"
                if msg != previous_message:
                    await event.edit(msg)
                    previous_message = msg
                    await asyncio.sleep(15)
            else:
                msg = file.error_message
                await event.edit(f"`{msg}`")
                return
        except Exception as e:
            LOGS.info(str(e))
            pass
    file = aria2.get_download(gid)
    complete = file.is_complete
    if complete:
        await event.edit(f"`Download complete !!`\
        \nSaved as: `{file.name}`")


CMD_HELP.update({
    "aria":
    ".aria_dl [URL] (or) .magnet [Magnet Link] (or) .torrent [path to torrent file]\
    \nUsage: Downloads the file into your userbot server storage.\
    \n\n.aria_pause (or) .aria_resume\
    \nUsage: Pauses/resumes on-going downloads.\
    \n\n.aria_clr\
    \nUsage: Clears the download queue, deleting all on-going downloads.\
    \n\n.aria_stats\
    \nUsage: Shows progress of the on-going downloads."
})
