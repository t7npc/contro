import asyncio, logging, os, re, sys
from pathlib import Path
import discord
from discord import app_commands
from discord.ext import commands
from cryptography.fernet import Fernet
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()
TOKEN=os.getenv('MTUyNzM1NTQ4NjY3MDk1MDUwMQ.GCwdJP.OxaQDJUWW0aNzT6L12MhlTdDUqf2Ac4wUOj-xU','').strip(); OWNER_ID=int(os.getenv('1523681366468853851','0') or 0)
MONGO_URI=os.getenv('MONGODB_URI','').strip(); ENC_KEY=os.getenv('TOKEN_ENCRYPTION_KEY','').strip()
AUDIO_DIR=Path(os.getenv('AUDIO_DIR','/app/audio')); MEDIA_DIR=AUDIO_DIR/'library'
MAX_BOTS=int(os.getenv('MAX_BOTS','5')); MAX_UPLOAD_MB=int(os.getenv('MAX_UPLOAD_MB','25'))
VOLUME=min(1.0,max(0.05,float(os.getenv('DEFAULT_VOLUME','0.65'))))
logging.basicConfig(level=getattr(logging,os.getenv('LOG_LEVEL','INFO').upper(),logging.INFO),format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')
log=logging.getLogger('karuppu')
if not TOKEN or not OWNER_ID or not MONGO_URI or not ENC_KEY:
    raise RuntimeError('Set DISCORD_TOKEN, OWNER_ID, MONGODB_URI and TOKEN_ENCRYPTION_KEY.')
try: cipher=Fernet(ENC_KEY.encode())
except Exception as e: raise RuntimeError('TOKEN_ENCRYPTION_KEY must be a valid Fernet key.') from e
AUDIO_DIR.mkdir(parents=True,exist_ok=True); MEDIA_DIR.mkdir(parents=True,exist_ok=True)
mongo=AsyncIOMotorClient(MONGO_URI); db=mongo['karuppu_contro']; bots_db=db['discord_bots']; media_db=db['media']
RED=discord.Color.from_rgb(170,20,35)
def embed(title,desc):
    e=discord.Embed(title=f'⚔️ {title.upper()}',description=desc,color=RED); e.set_footer(text='KARUPPU CONTRO BOT • DR CODES'); return e
def admin(i): return bool(i.guild and isinstance(i.user,discord.Member) and i.user.guild_permissions.administrator)
def safe_name(s): return re.sub(r'[^a-zA-Z0-9_-]+','_',s.strip()).strip('_')[:48] or 'media'
def admin_check():
    async def pred(i):
        if not admin(i): raise app_commands.CheckFailure('Administrator permission required.')
        return True
    return app_commands.check(pred)

class Worker(discord.Client):
    def __init__(self,label):
        intents=discord.Intents.none(); intents.guilds=True
        super().__init__(intents=intents); self.label=label
    async def join_and_play(self,channel_id,path,video=False):
        channel=self.get_channel(channel_id) or await self.fetch_channel(channel_id)
        if not isinstance(channel,(discord.VoiceChannel,discord.StageChannel)): raise RuntimeError('Voice channel unavailable')
        vc=discord.utils.get(self.voice_clients,guild=channel.guild)
        if vc is None or not vc.is_connected(): vc=await channel.connect()
        if vc.is_playing() or vc.is_paused(): vc.stop()
        src=discord.FFmpegPCMAudio(str(path),options='-vn' if video else '')
        vc.play(discord.PCMVolumeTransformer(src,volume=VOLUME)); return vc
    async def stop_audio(self):
        for vc in list(self.voice_clients):
            if vc.is_playing() or vc.is_paused(): vc.stop()
    async def leave(self):
        for vc in list(self.voice_clients): await vc.disconnect(force=True)

class Fleet:
    def __init__(self): self.clients={}; self.tasks={}
    async def add(self,name,token):
        key=name.casefold()
        if key in self.clients: raise ValueError('Bot name already exists')
        if len(self.clients)>=MAX_BOTS: raise ValueError('Bot limit reached')
        c=Worker(name); task=asyncio.create_task(c.start(token)); self.clients[key]=c; self.tasks[key]=task
        try: await asyncio.wait_for(c.wait_until_ready(),30)
        except Exception:
            self.clients.pop(key,None); self.tasks.pop(key,None); task.cancel(); await asyncio.gather(task,return_exceptions=True)
            raise RuntimeError('Bot could not log in. Verify its bot token.')
        return c
    async def remove(self,name):
        key=name.casefold(); c=self.clients.pop(key,None); t=self.tasks.pop(key,None)
        if c: await c.close()
        if t: await asyncio.gather(t,return_exceptions=True)
    def choose(self,selection):
        items=list(self.clients.items())
        if selection.strip().lower()=='all': return items
        nums=[int(x.strip()) for x in selection.split(',') if x.strip().isdigit()]
        return [items[n-1] for n in nums if 1<=n<=len(items)]
    async def close(self):
        for key in list(self.clients): await self.remove(key)
fleet=Fleet()

class AddBotModal(discord.ui.Modal,title='Register a Discord bot'):
    name=discord.ui.TextInput(label='Bot display name',placeholder='Karuppu-02',max_length=32)
    token=discord.ui.TextInput(label='Bot token — keep private',style=discord.TextStyle.paragraph,max_length=100)
    async def on_submit(self,i):
        if not admin(i): return await i.response.send_message('அனுமதி இல்லை. இந்தக் கட்டுப்பாடு நிர்வாகிகளுக்கே.',ephemeral=True)
        name=str(self.name.value).strip(); token=str(self.token.value).strip()
        await i.response.defer(ephemeral=True,thinking=True)
        try:
            c=await fleet.add(name,token)
            await bots_db.update_one({'key':name.casefold()},{'$set':{'name':name,'key':name.casefold(),'token':cipher.encrypt(token.encode()).decode(),'user_id':c.user.id if c.user else None}},upsert=True)
            await i.followup.send(f'🛡️ **{discord.utils.escape_markdown(name)}** பதிவு செய்யப்பட்டது. இதை server-ல் invite செய்து Connect/Speak permission கொடுக்கவும்.',ephemeral=True)
        except Exception as e:
            log.warning('Add bot failed: %s',e); await i.followup.send('Bot சேர்க்க முடியவில்லை. Token, bot limit மற்றும் application நிலையைச் சரிபார்க்கவும்.',ephemeral=True)

class WelcomeView(discord.ui.View):
    @discord.ui.button(label='ABOUT',style=discord.ButtonStyle.secondary,emoji='🛡️')
    async def about(self,i,b):
        await i.response.send_message(embed=embed('About Karuppu',f'**KARUPPU CONTRO BOT**\nபல bot கணக்குகள் — ஒரே கட்டுப்பாடு.\n\n**PYTHON:** `{sys.version.split()[0]}`\n**DATABASE:** `MongoDB`\n**DEVELOPED BY:** `@Mystery-1431`\n**TOKEN BY:** `DR CODES`'),ephemeral=True)
    @discord.ui.button(label='COMMANDS',style=discord.ButtonStyle.danger,emoji='📜')
    async def commands(self,i,b):
        await i.response.send_message(embed=embed('Command Scroll','`/add_bot` `/remove_bot` `/bots` `/join`\n`/add` `/save_media` `/media` `/play` `/vplay`\n`/stop` `/vstop` `/remove_media`'),ephemeral=True)
    @discord.ui.button(label='ADMIN PANEL',style=discord.ButtonStyle.primary,emoji='⚙️')
    async def panel(self,i,b):
        if not admin(i): return await i.response.send_message('இந்த வாசல் நிர்வாகிகளுக்கே.',ephemeral=True)
        await i.response.send_message(embed=embed('Admin Control','நிர்வாகியே, கட்டுப்பாடு உங்களிடம். `/add_bot` மூலம் bot சேர்க்கவும்; `/join` மூலம் voice-ல் இணைக்கவும்.'),ephemeral=True)

class Karuppu(commands.Bot):
    def __init__(self): super().__init__(command_prefix='!',intents=discord.Intents.default(),help_command=None)
    async def setup_hook(self):
        async for row in bots_db.find({}):
            try: await fleet.add(row['name'],cipher.decrypt(row['token'].encode()).decode())
            except Exception as e: log.error('Could not restore %s: %s',row.get('name'),e)
        synced=await self.tree.sync(); log.info('Synced %d slash commands',len(synced))
    async def close(self): await fleet.close(); mongo.close(); await super().close()
bot=Karuppu()

@bot.tree.command(name='start',description='Open the Karuppu welcome panel')
async def start(i):
    await i.response.send_message(embed=embed('காவல் தொடங்கியது','**KARUPPU CONTRO BOT**\nஅமைதியாக இருங்கள்; கட்டுப்பாடு இங்கே தொடங்குகிறது.\n\n🛡️ Multi-bot voice control\n🎵 Named audio library\n🎬 Video-file audio playback\n⚙️ Administrator controls\n\n*கட்டளை தெளிவாக இருக்கட்டும். செயல் ஒழுங்காக நடக்கட்டும்.*'),view=WelcomeView())

@bot.tree.command(name='add_bot',description='Register another Discord bot')
@admin_check()
async def add_bot(i): await i.response.send_modal(AddBotModal())

@bot.tree.command(name='remove_bot',description='Remove a registered bot')
@app_commands.describe(name='Registered bot name')
@admin_check()
async def remove_bot(i,name:str):
    row=await bots_db.find_one({'key':name.casefold()})
    if not row: return await i.response.send_message('அந்த பெயரில் bot இல்லை.',ephemeral=True)
    await fleet.remove(row['name']); await bots_db.delete_one({'_id':row['_id']})
    await i.response.send_message(f'🛡️ **{discord.utils.escape_markdown(name)}** நீக்கப்பட்டது.',ephemeral=True)

@bot.tree.command(name='bots',description='List registered bots')
@admin_check()
async def bots(i):
    rows=[]
    async for row in bots_db.find({}).sort('name',1):
        c=fleet.clients.get(row['key']); rows.append(f"**{discord.utils.escape_markdown(row['name'])}** — {'🟢 Online' if c and c.is_ready() else '🔴 Offline'}")
    await i.response.send_message(embed=embed('Bot Roster','\n'.join(rows) or 'No additional bots registered.'),ephemeral=True)

@bot.tree.command(name='join',description='Connect all registered bots to your current voice channel')
@admin_check()
async def join(i):
    if not isinstance(i.user,discord.Member) or not i.user.voice or not i.user.voice.channel:
        return await i.response.send_message('முதலில் voice channel-ல் நுழையுங்கள்.',ephemeral=True)
    await i.response.defer(ephemeral=True,thinking=True); ok=[]; bad=[]; channel_id=i.user.voice.channel.id
    for name,c in fleet.clients.items():
        try:
            await c.wait_until_ready(); ch=c.get_channel(channel_id) or await c.fetch_channel(channel_id); await ch.connect(); ok.append(name)
        except Exception as e: log.warning('Join %s failed: %s',name,e); bad.append(name)
    msg='🟢 Connected: '+(', '.join(ok) or 'none')
    if bad: msg+='\n🔴 Failed: '+', '.join(bad)+' — invite those bots and grant Connect/Speak.'
    if not fleet.clients: msg='No additional bots. Use `/add_bot` first.'
    await i.followup.send(embed=embed('Voice deployment',msg),ephemeral=True)

@bot.tree.command(name='add',description='Show how to add named audio/video media')
@admin_check()
async def add(i):
    await i.response.send_message(embed=embed('Media Library','Upload media with `/save_media name:<name> kind:<audio/video> file:<attachment>`.\n\nFiles are stored on the Railway volume; metadata is stored in MongoDB.'),ephemeral=True)

@bot.tree.command(name='save_media',description='Save an uploaded audio or video file with a name')
@app_commands.describe(name='Name used for playback',kind='Audio or Video',file='Media attachment')
@app_commands.choices(kind=[app_commands.Choice(name='Audio',value='audio'),app_commands.Choice(name='Video',value='video')])
@admin_check()
async def save_media(i,name:str,kind:app_commands.Choice[str],file:discord.Attachment):
    if file.size>MAX_UPLOAD_MB*1024*1024: return await i.response.send_message(f'File exceeds {MAX_UPLOAD_MB} MB.',ephemeral=True)
    ext=Path(file.filename).suffix.lower(); audio={'.mp3','.wav','.ogg','.m4a','.flac'}; video={'.mp4','.mov','.mkv','.webm'}
    if ext not in audio|video or (kind.value=='audio' and ext not in audio) or (kind.value=='video' and ext not in video):
        return await i.response.send_message('Unsupported file extension or media type.',ephemeral=True)
    key=safe_name(name).casefold()
    if await media_db.find_one({'key':key}): return await i.response.send_message('That media name already exists.',ephemeral=True)
    filename=safe_name(name)+ext; path=MEDIA_DIR/filename; path.write_bytes(await file.read())
    await media_db.insert_one({'name':name.strip(),'key':key,'kind':kind.value,'filename':filename,'size':file.size,'added_by':i.user.id})
    await i.response.send_message(embed=embed('Media Sealed',f'**{discord.utils.escape_markdown(name)}** added to the {kind.value} library.'),ephemeral=True)

async def play_media(i,name,selection,kind):
    if not isinstance(i.user,discord.Member) or not i.user.voice or not i.user.voice.channel: return await i.response.send_message('முதலில் voice channel-ல் நுழையுங்கள்.',ephemeral=True)
    row=await media_db.find_one({'key':safe_name(name).casefold(),'kind':kind})
    if not row: return await i.response.send_message('Media கிடைக்கவில்லை. `/media` மூலம் பெயரைப் பாருங்கள்.',ephemeral=True)
    path=MEDIA_DIR/row['filename']
    if not path.is_file(): return await i.response.send_message('Stored file missing. Please upload it again.',ephemeral=True)
    targets=fleet.choose(selection)
    if not targets: return await i.response.send_message('No selected registered bots. Use `all` or bot numbers.',ephemeral=True)
    await i.response.defer(ephemeral=True,thinking=True); ok=[]; bad=[]
    for label,c in targets:
        try: await c.wait_until_ready(); await c.join_and_play(i.user.voice.channel.id,path,video=(kind=='video')); ok.append(label)
        except Exception as e: log.warning('Playback %s failed: %s',label,e); bad.append(label)
    msg='🟢 Started: '+(', '.join(ok) or 'none')
    if bad: msg+='\n🔴 Failed: '+', '.join(bad)
    if kind=='video': msg+='\n\nDiscord voice transmits audio only; this plays the video audio track.'
    await i.followup.send(embed=embed('Transmission Started',msg),ephemeral=True)

@bot.tree.command(name='play',description='Play a saved audio file')
@app_commands.describe(name='Saved audio name',bots='all or bot numbers such as 1,2')
@admin_check()
async def play(i,name:str,bots:str='all'): await play_media(i,name,bots,'audio')

@bot.tree.command(name='vplay',description='Play the audio track from a saved video')
@app_commands.describe(name='Saved video name',bots='all or bot numbers such as 1,2')
@admin_check()
async def vplay(i,name:str,bots:str='all'): await play_media(i,name,bots,'video')

async def stop_selected(i,selection):
    targets=fleet.choose(selection)
    for _,c in targets: await c.stop_audio()
    await i.response.send_message(embed=embed('Playback Halted','Stopped: '+(', '.join(n for n,_ in targets) or 'no selected bots')),ephemeral=True)
@bot.tree.command(name='stop',description='Stop audio playback')
@app_commands.describe(bots='all or bot numbers')
@admin_check()
async def stop(i,bots:str='all'): await stop_selected(i,bots)
@bot.tree.command(name='vstop',description='Stop video-file audio playback')
@app_commands.describe(bots='all or bot numbers')
@admin_check()
async def vstop(i,bots:str='all'): await stop_selected(i,bots)

@bot.tree.command(name='media',description='List saved audio and video')
@admin_check()
async def media(i):
    lines=[]
    async for row in media_db.find({}).sort('name',1).limit(40): lines.append(('🎵' if row['kind']=='audio' else '🎬')+f" **{discord.utils.escape_markdown(row['name'])}** — `{row['kind']}`")
    await i.response.send_message(embed=embed('Stored Media','\n'.join(lines) or 'Library is empty.'),ephemeral=True)

@bot.tree.command(name='remove_media',description='Delete a saved media file')
@app_commands.describe(name='Saved media name')
@admin_check()
async def remove_media(i,name:str):
    row=await media_db.find_one({'key':safe_name(name).casefold()})
    if not row: return await i.response.send_message('Media not found.',ephemeral=True)
    path=MEDIA_DIR/row['filename']
    if path.exists(): path.unlink()
    await media_db.delete_one({'_id':row['_id']})
    await i.response.send_message(f'🗑️ **{discord.utils.escape_markdown(name)}** removed.',ephemeral=True)

@bot.tree.error
async def command_error(i,error):
    if isinstance(error,app_commands.CheckFailure): msg='இந்தக் கட்டுப்பாடு server administrators-க்கே.'
    else: log.error('Command error: %r',error); msg='கட்டளையில் பிழை. Railway logs-ஐச் சரிபார்க்கவும்.'
    if i.response.is_done(): await i.followup.send(msg,ephemeral=True)
    else: await i.response.send_message(msg,ephemeral=True)

bot.run(TOKEN)
