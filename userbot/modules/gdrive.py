# Copyright (C) 2019 The Raphielscape Company LLC.
#
# Licensed under the Raphielscape Public License, Version 1.c (the "License");
# you may not use this file except in compliance with the License.
#
# thanks to @adekmaulana for the Improvement

import os
import pickle
import codecs
import asyncio
import math
import time
import re
import binascii
from os.path import isfile, isdir
from mimetypes import guess_type

from telethon import events

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from googleapiclient.http import MediaFileUpload

from userbot import (G_DRIVE_CLIENT_ID, G_DRIVE_CLIENT_SECRET,
                     G_DRIVE_AUTH_TOKEN_DATA, BOTLOG_CHATID,
                     TEMP_DOWNLOAD_DIRECTORY, CMD_HELP, LOGS,
                     G_DRIVE_FOLDER_ID)
from userbot.events import register
from userbot.modules.upload_download import humanbytes, time_formatter
# =========================================================== #
#                          STATIC                             #
# =========================================================== #
GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.metadata"
]
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
# =========================================================== #
#      STATIC CASE FOR G_DRIVE_FOLDER_ID IF VALUE IS URL      #
# =========================================================== #
__ = G_DRIVE_FOLDER_ID
if __ is not None:
    if "uc?id=" in G_DRIVE_FOLDER_ID:
        LOGS.info(
            "G_DRIVE_FOLDER_ID is not a valid folderURL...")
        G_DRIVE_FOLDER_ID = None
    try:
        G_DRIVE_FOLDER_ID = __.split("folders/")[1]
    except IndexError:
        try:
            G_DRIVE_FOLDER_ID = __.split("open?id=")[1]
        except IndexError:
            try:
                if "/view" in __:
                    G_DRIVE_FOLDER_ID = __.split("/")[-2]
            except IndexError:
                try:
                    G_DRIVE_FOLDER_ID = __.split(
                                      "folderview?id=")[1]
                except IndexError:
                    if any(map(str.isdigit, __)):
                        _1 = True
                    else:
                        _1 = False
                    if "-" in __ or "_" in __:
                        _2 = True
                    else:
                        _2 = False
                    if True in [_1 or _2]:
                        pass
                    else:
                        LOGS.info(
                           "G_DRIVE_FOLDER_ID not valid...")
# =========================================================== #
#                                                             #
# =========================================================== #


async def progress(current, total, event, start, type_of_ps, file_name=None):
    """Generic progress_callback for uploads and downloads."""
    now = time.time()
    diff = now - start
    if round(diff % 10.00) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff
        elapsed_time = round(diff) * 1000
        time_to_completion = round((total - current) / speed) * 1000
        estimated_total_time = elapsed_time + time_to_completion
        progress_str = "`Downloading...` | [{0}{1}] `{2}%`\n".format(
            ''.join(["**#**" for i in range(math.floor(percentage / 10))]),
            ''.join(["**-**" for i in range(10 - math.floor(percentage / 10))]),
            round(percentage, 2))
        tmp = (progress_str + "\n" +
               f"{humanbytes(current)} of {humanbytes(total)}\n"
               f"ETA: {time_formatter(estimated_total_time)}"
               )
        if file_name:
            await event.edit(f"{type_of_ps}\n\n"
                             f" • `Name   :` `{file_name}`"
                             f" • `Status :`\n    {tmp}")
        else:
            await event.edit(f"{type_of_ps}\n\n"
                             f" • `Status :`\n    {tmp}")


async def get_raw_name(file_path):
    """ - Get file_name from file_path - """
    return file_path.split("/")[-1]


async def get_mimeType(name):
    """ - Check mimeType given file - """
    mimeType = guess_type(name)[0]
    if not mimeType:
        mimeType = 'text/plain'
    return mimeType


@register(pattern="^.gdf (mkdir|rm|chck)(.*)", outgoing=True)
async def google_drive_managers(gdrive):
    """ - Google Drive folder/file management - """
    await gdrive.edit("`Sending information...`")
    service = await create_app(gdrive)
    f_name = gdrive.pattern_match.group(2).strip()
    exe = gdrive.pattern_match.group(1)
    """ - Only if given value are mkdir - """
    metadata = {
        'name': f_name,
        'mimeType': 'application/vnd.google-apps.folder',
    }
    try:
        if parent_Id is not None:
            pass
    except NameError:
        """ - Fallback to G_DRIVE_FOLDER_ID else to root dir - """
        if G_DRIVE_FOLDER_ID is not None:
            metadata['parents'] = [G_DRIVE_FOLDER_ID]
    else:
        """ - Override G_DRIVE_FOLDER_ID because parent_Id not empty - """
        metadata['parents'] = [parent_Id]
    permission = {
        "role": "reader",
        "type": "anyone",
        "allowFileDiscovery": True,
        "value": None,
    }
    page_token = None
    result = service.files().list(
        q=f'name="{f_name}"',
        spaces='drive',
        fields=(
            'nextPageToken, files(parents, name, id, '
            'mimeType, webViewLink, webContentLink, description)'
        ),
        pageToken=page_token
    ).execute()
    if exe == "mkdir":
        """ - Create a directory, abort if exist when parent not given - """
        status = "[FOLDER - EXIST]"
        try:
            folder = result.get('files', [])[0]
        except IndexError:
            folder = service.files().create(
                   body=metadata,
                   fields="id, webViewLink"
             ).execute()
            status = status.replace("EXIST]", "CREATED]")
        folder_id = folder.get('id')
        webViewURL = folder.get('webViewLink')
        if "CREATED" in status:
            """ - Change permission - """
            try:
                service.permissions().create(
                   fileId=folder_id, body=permission).execute()
            except HttpError as e:
                return await gdrive.edit("`" + str(e) + "`")
        await gdrive.edit(
            f"`{status}`\n\n"
            f" • `Name :` `{f_name}`\n"
            f" • `ID   :` `{folder_id}`\n"
            f" • `URL  :` [Open]({webViewURL})"
        )
    elif exe == "rm":
        """ - Permanently delete, skipping the trash - """
        try:
            """ - Try if given value is a name not a folderId/fileId - """
            f = result.get('files', [])[0]
            f_id = f.get('id')
        except IndexError:
            """ - If failed assumming value is folderId/fileId - """
            f_id = f_name
            try:
                f = service.files().get(fileId=f_id,
                                        fields="mimeType").execute()
            except Exception as e:
                return await gdrive.edit(
                    f"`[FILE/FOLDER - ERROR]`\n\n"
                    f" • `Status :` `{str(e)}`"
                )
        mimeType = f.get('mimeType')
        if mimeType == 'application/vnd.google-apps.folder':
            status = "[FOLDER - DELETE]"
        else:
            status = "[FILE - DELETE]"
        try:
            service.files().delete(fileId=f_id).execute()
        except HttpError as e:
            status.replace("DELETE]", "ERROR]")
            return await gdrive.edit(
                f"`{status}`\n\n"
                f" • `Status :` `{str(e)}`"
            )
        else:
            await gdrive.edit(
                    f"`{status}`\n\n"
                    " • `Status :` `OK`"
            )
    elif exe == "chck":
        """ - Check file/folder if exists - """
        try:
            f = result.get('files', [])[0]
        except IndexError:
            """ - If failed assumming value is folderId/fileId - """
            f_id = f_name
            try:
                f = service.files().get(
                       fileId=f_id,
                       fields="name, id, mimeType, "
                              "webViewLink, webContentLink, description"
                ).execute()
            except Exception as e:
                return await gdrive.edit(
                    "`[FILE/FOLDER - ERROR]`\n\n"
                    " • `Status :` **BAD**\n"
                    f" • `Reason :` `{str(e)}`"
                )
        """ - If exists parse file/folder information - """
        f_name = f.get('name')  # override input value
        f_id = f.get('id')
        mimeType = f.get('mimeType')
        webViewLink = f.get('webViewLink')
        downloadURL = f.get('webContentLink')
        description = f.get('description')
        if mimeType == "application/vnd.google-apps.folder":
            status = "[FOLDER - EXIST]"
        else:
            status = "[FILE - EXIST]"
        msg = (
            f"`{status}`\n\n"
            f" • `Name     :` `{f_name}`\n"
            f" • `ID       :` `{f_id}`\n"
            f" • `URL      :` [Open]({webViewLink})\n"
        )
        if mimeType != "application/vnd.google-apps.folder":
            msg += f" • `Download :` [{f_name}]({downloadURL})\n"
        if description:
            msg += f" • `About    :`\n    `{description}`"
        await gdrive.edit(msg)
    page_token = result.get('nextPageToken', None)
    return


@register(pattern="^.gd(?: |$)(.*)", outgoing=True)
async def google_drive(gdrive):
    """ - Parsing all google drive function - """
    file_path = gdrive.pattern_match.group(1)
    if not file_path and not gdrive.reply_to_msg_id:
        return
    if isdir(file_path):
        return await gdrive.edit(
            "`[FOLDER - ERROR]`\n\n"
            " • `Status :` **BAD**\n"
            " • `Reason :` Folder upload not supported."
        )
    if file_path and gdrive.reply_to_msg_id:
        return await gdrive.edit(
            "`[UNKNOWN - ERROR]`\n\n"
            " • `Status :` **FAILED**\n"
            f" • `Reason :` Confused to upload file or the replied message/media."
        )
    service = await create_app(gdrive)
    if not file_path and gdrive.reply_to_msg_id:
        return await download(gdrive, service)
    mimeType = await get_mimeType(file_path)
    file_name = await get_raw_name(file_path)
    viewURL, downloadURL = await upload(
                         gdrive, service, file_path, file_name, mimeType)
    if viewURL and downloadURL:
        await gdrive.edit(
            "`[FILE - UPLOAD]`\n\n"
            f" • `Name     :` `{file_name}`\n"
            " • `Status   :` **OK**\n"
            f" • `URL      :` [{file_name}]({viewURL})\n"
            f" • `Download :` [{file_name}]({downloadURL})"
        )
    return


async def download(gdrive, service, file_path=None, file_name=None, url=None):
    """ - Download files to local then upload - """
    if not isdir(TEMP_DOWNLOAD_DIRECTORY):
        os.makedirs(TEMP_DOWNLOAD_DIRECTORY)
        required_file_name = None
    if file_path is None and file_name is None and url is None:
        try:
            current_time = time.time()
            downloaded_file_name = await gdrive.client.download_media(
                await gdrive.get_reply_message(),
                TEMP_DOWNLOAD_DIRECTORY,
                progress_callback=lambda d, t: asyncio.get_event_loop(
                ).create_task(progress(d, t, gdrive, current_time,
                                       "`[FILE - DOWNLOAD]`")))
        except Exception as e:
            await gdrive.edit(str(e))
        else:
            required_file_name = downloaded_file_name
            file_name = await get_raw_name(required_file_name)
            mimeType = await get_mimeType(required_file_name)
            await gdrive.edit(
                f"`[FILE - DOWNLOAD]`\n\n"
                f" • `Name   :` `{file_name}`\n"
                " • `Status :` **OK**\n\n"
                "Successfully downloaded.\n"
                "Initiating Upload to Google Drive..."
            )
            try:
                result = await upload(gdrive, service, required_file_name,
                                      file_name, mimeType)
                await gdrive.edit(
                    "`[FILE - DOWNLOAD]`\n\n"
                    f" • `Name     :` `{file_name}`\n"
                    " • `Status   :` **OK**\n"
                    f" • `URL      :` [{file_name}]({result[0]})\n"
                    f" • `Download :` [{file_name}]({result[1]})"
                )
            except Exception as e:
                return await gdrive.edit(
                    "`[FILE - ERROR]`\n\n"
                    f" • `Name   :` `{file_name}`\n"
                    " • `Status :` **BAD**\n"
                    f" • `Reason :` failed to upload.\n"
                    f"    `{str(e)}`"
                )
    return


async def upload(gdrive, service, file_path, file_name, mimeType):
    await gdrive.edit("`Processing upload...`")
    body = {
        "name": file_name,
        "description": "Uploaded from Telegram using ProjectBish userbot.",
        "mimeType": mimeType,
    }
    try:
        if parent_Id is not None:
            pass
    except NameError:
        """ - Fallback to G_DRIVE_FOLDER_ID else root dir - """
        if G_DRIVE_FOLDER_ID is not None:
            body['parents'] = [G_DRIVE_FOLDER_ID]
    else:
        """ - Override G_DRIVE_FOLDER_ID because parent_Id not empty - """
        body['parents'] = [parent_Id]
    permission = {
        "role": "reader",
        "type": "anyone",
        "allowFileDiscovery": True,
        "value": None,
    }
    media_body = MediaFileUpload(
        file_path,
        mimetype=mimeType,
        resumable=True
    )
    """ - Start upload process - """
    response = None
    display_message = None
    file = service.files().create(body=body, media_body=media_body,
                                  fields="id, webContentLink, webViewLink")
    while response is None:
        status, response = file.next_chunk()
        await asyncio.sleep(0.3)
        if status:
            percentage = int(status.progress() * 100)
            prog_str = "`Uploading...` | [{0}{1}] `{2}%`".format(
                "".join(["**#**" for i in range(math.floor(percentage / 10))]),
                "".join(["**-**"
                         for i in range(10 - math.floor(percentage / 10))]),
                round(percentage, 2))
            current_message = (
                "`[FILE - UPLOAD]`\n\n"
                f" • `Name   :` `{file_name}`\n"
                " • `Status :`\n"
                f"    {prog_str}"
            )
            if display_message != current_message:
                try:
                    await gdrive.edit(current_message)
                    display_message = current_message
                except Exception:
                    pass
    file_id = response.get("id")
    viewURL = response.get("webViewLink")
    downloadURL = response.get("webContentLink")
    """ - Change permission - """
    try:
        service.permissions().create(fileId=file_id, body=permission).execute()
    except HttpError as e:
        return await gdrive.edit("`" + str(e) + "`")
    return viewURL, downloadURL


@register(pattern="^.gdfset (put|rm)(?: |$)(.*)", outgoing=True)
async def set_upload_folder(gdrive):
    """ - Set parents dir for upload/check/makedir/remove - """
    await gdrive.edit("`Sending information...`")
    global parent_Id
    exe = gdrive.pattern_match.group(1)
    if exe == "rm":
        if G_DRIVE_FOLDER_ID is not None:
            parent_Id = G_DRIVE_FOLDER_ID
            return await gdrive.edit(
                "`[FOLDER - SET]`\n\n"
                " • `Status :` **OK**\n"
                " • `Reason :` upload will use `G_DRIVE_FOLDER_ID`,\n"
                "    as parentId for next."
            )
        else:
            parent_Id = None
            return await gdrive.edit(
                "`[FOLDER - SET]`\n\n"
                " • `Status :` **OK**\n"
                " • `Reason :` `G_DRIVE_FOLDER_ID` is empty,\n"
                "    upload will use root dir.")
    inp = gdrive.pattern_match.group(2)
    if not inp:
        return await gdrive.edit(">`.gdfset put <folderURL/folderID>`")
    """ - Value for .gdfset (put|rm) can be folderId or folder link - """
    try:
        ext_id = re.findall(r'\bhttps?://drive\.google\.com\S+', inp)[0]
    except IndexError:
        """ - if given value isn't folderURL assume it's an Id - """
        if any(map(str.isdigit, inp)):
            c1 = True
        else:
            c1 = False
        if "-" in inp or "_" in inp:
            c2 = True
        else:
            c2 = False
        if True in [c1 or c2]:
            parent_Id = inp
            await gdrive.edit(
                "`[PARENT - FOLDER]`\n\n"
                " • `Status :` **OK**\n"
                " • `Reason :` Successfully changed."
            )
        parent_Id = inp
    else:
        if "uc?id=" in ext_id:
            return await gdrive.edit(
                "`[URL - ERROR]`\n\n"
                " • `Status :` **BAD**\n"
                " • `Reason :` Not a valid folderURL"
            )
        try:
            parent_Id = ext_id.split("folders/")[1]
        except IndexError:
            """ - Try catch again if URL open?id= - """
            try:
                parent_Id = ext_id.split("open?id=")[1]
            except IndexError:
                try:
                    if "/view" in ext_id:
                        parent_Id = ext_id.split("/")[-2]
                except IndexError:
                    """ - Last attemp to catch - """
                    try:
                        parent_Id = ext_id.split("folderview?id=")[1]
                    except IndexError:
                        return await gdrive.edit(
                            "`[URL - ERROR]`\n\n"
                            " • `Status :` **BAD**\n"
                            " • `Reason :` Not a valid folderURL or empty"
                        )
        await gdrive.edit(
                "`[PARENT - FOLDER]`\n\n"
                " • `Status :` **OK**\n"
                " • `Reason :` Successfully changed."
        )
    return parent_Id


async def generate_credentials(gdrive):
    """ - Generate credentials - """
    error_msg = (
        "`[TOKEN - ERROR]`\n\n"
        " • `Status :` **RISK**\n"
        " • `Reason :` There is data corruption or a security violation.\n\n"
        "`It's probably your` **G_DRIVE_TOKEN_DATA** `is not match\n"
        "Or you still use the old gdrive module token data!.\n"
        "Please change it, by deleting` **G_DRIVE_TOKEN_DATA** "
        "`from your ConfigVars and regenerate the token and put it again`."
    )
    configs = {
        "installed": {
            "client_id": G_DRIVE_CLIENT_ID,
            "client_secret": G_DRIVE_CLIENT_SECRET,
            "auth_uri": GOOGLE_AUTH_URI,
            "token_uri": GOOGLE_TOKEN_URI,
        }
    }
    creds = None
    try:
        if G_DRIVE_AUTH_TOKEN_DATA is not None:
            """ - Repack credential objects from strings - """
            try:
                creds = pickle.loads(
                      codecs.decode(G_DRIVE_AUTH_TOKEN_DATA.encode(), "base64"))
            except pickle.UnpicklingError:
                return await gdrive.edit(error_msg)
        else:
            if isfile("auth.txt"):
                """ - Load credentials from file if exists - """
                with open("auth.txt", "r") as token:
                    creds = token.read()
                    try:
                        creds = pickle.loads(
                              codecs.decode(creds.encode(), "base64"))
                    except pickle.UnpicklingError:
                        return await gdrive.edit(error_msg)
    except binascii.Error as e:
        return await gdrive.edit(
            "`[TOKEN - ERROR]`\n\n"
            " • `Status :` **BAD**\n"
            " • `Reason :` Invalid credentials or token data.\n"
            f"    -> `{str(e)}`\n\n"
            "`if you copy paste from 'auth.txt' file and still error "
            "try use MiXplorer file manager and open as code editor or "
            "if you don't want to download just run command`\n"
            ">`.term cat auth.txt`\n"
            "Cp and paste to `G_DRIVE_AUTH_TOKEN_DATA` heroku ConfigVars or\n"
            ">`.set var G_DRIVE_AUTH_TOKEN_DATA <token you get>`\n\n"
            "Or if you still have value from old module remove it first!, "
            "because my module use v3 api while the old is using v2 api...\n"
            ">`.del var G_DRIVE_AUTH_TOKEN_DATA` to delete the old token data."
        )
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            await gdrive.edit("`Refreshing credentials...`")
            """ - Refresh credentials - """
            creds.refresh(Request())
        else:
            """ - Create credentials - """
            await gdrive.edit("`Creating credentials...`")
            flow = InstalledAppFlow.from_client_config(
                 configs, SCOPES, redirect_uri=REDIRECT_URI)
            auth_url, _ = flow.authorization_url(
                        access_type='offline', prompt='consent')
            msg = await gdrive.respond(
                "`Go to your BOTLOG chat to authenticate`"
                " **G_DRIVE_AUTH_TOKEN_DATA**"
            )
            async with gdrive.client.conversation(BOTLOG_CHATID) as conv:
                await conv.send_message(
                    "Please go to this URL:\n"
                    f"{auth_url}\nauthorize then reply the code"
                )
                r = conv.wait_event(
                  events.NewMessage(outgoing=True, chats=BOTLOG_CHATID))
                r = await r
                code = r.message.message.strip()
                flow.fetch_token(code=code)
                creds = flow.credentials
                await gdrive.client.delete_messages(gdrive.chat_id, msg.id)
            """ - Unpack credential objects into strings - """
            if G_DRIVE_AUTH_TOKEN_DATA is None:
                with open("auth.txt", "w") as f:
                    pickled = codecs.encode(
                            pickle.dumps(creds), "base64").decode()
                    """ - Put into file to use it later - """
                    f.write(pickled)
            await gdrive.client.send_file(
                BOTLOG_CHATID, "auth.txt",
                caption=("This is your `G_DRIVE_AUTH_TOKEN_DATA`, "
                         "open then copy and paste to your heroku ConfigVars, "
                         "or do:\n>`.set var G_DRIVE_AUTH_TOKEN_DATA "
                         "<value inside auth.txt>`")
            )
            msg = await gdrive.respond(
                "`Go to your BOTLOG chat to get` **G_DRIVE_AUTH_TOKEN_DATA**\n"
                "`The next time you called the command you didn't need to "
                "authenticate anymore as long there is a valid file 'auth.txt'"
                " or, you already put the value from 'auth.txt'"
                " to your heroku app ConfigVars.` **G_DRIVE_AUTH_TOKEN_DATA**"
            )
            await asyncio.sleep(3.5)
            await gdrive.client.delete_messages(gdrive.chat_id, msg.id)
    return creds


async def create_app(gdrive):
    """ - Create google drive service app - """
    creds = await generate_credentials(gdrive)
    service = build('drive', 'v3', credentials=creds, cache_discovery=False)
    return service


CMD_HELP.update({
    "gdrive":
    ".gd"
    "\nUsage: Upload file into google drive"
    "\n\n.gdf mkdir <folder name>"
    "\nUsage: create google drive folder"
    "\n\n.gdf chck <folder/file|name/id>"
    "\nUsage: check given value is exist or no"
    "\n\n.gdf rm <folder/file|name/id>"
    "\nUsage: delete a file/folder, and can't be undone"
    "\nThis method skipping file trash, so be caution..."
    "\n\n.gdfset put <folderURL/folderID>"
    "\nUsage: change upload directory"
    "\n\n.gdfset rm"
    "\nUsage: remove set parentId from .gdfset put <value> "
    "to **G_DRIVE_FOLDER_ID** and if empty upload will go to root."
})