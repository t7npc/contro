# KARUPPU CONTRO BOT
Multi-bot Discord voice controller • Created by @Mystery-1431 • Token by DR CODES

## Features
- `/start` welcome panel with ABOUT, COMMANDS and ADMIN PANEL buttons
- `/add_bot` securely registers another official Discord bot using a private modal
- `/remove_bot`, `/bots`, `/join`
- `/add` media guide and `/save_media` named audio/video uploads
- `/media`, `/play`, `/vplay`, `/stop`, `/vstop`, `/remove_media`
- MongoDB stores encrypted additional bot tokens and media metadata
- Railway Volume stores media files

## Video limitation
Discord voice channels carry audio. The standard Discord bot voice API cannot broadcast an uploaded video as a video stream. `/vplay` plays the video's audio track only.

## Railway environment variables
`DISCORD_TOKEN` master bot token (required)
`OWNER_ID` owner Discord user ID (required)
`MONGODB_URI` MongoDB connection URI (required)
`TOKEN_ENCRYPTION_KEY` Fernet encryption key (required)
`AUDIO_DIR=/app/audio`
`MAX_BOTS=5`
`MAX_UPLOAD_MB=25`
`DEFAULT_VOLUME=0.65`
`LOG_LEVEL=INFO`

Generate the encryption key locally:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Keep the same key permanently. If lost or changed, stored child-bot tokens cannot be decrypted.

## Deploy
1. Push this folder to GitHub and deploy it on Railway.
2. Add the environment variables above in Railway Variables.
3. Attach a Railway Volume mounted at `/app/audio` so uploaded files survive redeploys.
4. Use MongoDB Atlas or another MongoDB-compatible service for `MONGODB_URI`.
5. Invite the master bot and each added bot to the same server with View Channels, Connect, Speak and required text/application-command permissions.
6. Use `/start`, then `/add_bot`; add files with `/save_media`.

## Use
- Join a voice channel, then `/join`.
- `/play name:<saved-name> bots:all` plays audio on every registered bot.
- `/play name:<saved-name> bots:1,2` selects bots by current alphabetical roster order.
- `/vplay` plays the audio track from a saved video.
- `/stop` and `/vstop` stop playback.

## Security
Use only official bot tokens for bots you own or are authorized to operate. Never publish tokens, MongoDB credentials, `.env`, or the Fernet key. Additional bot tokens are encrypted in MongoDB; anyone with both database access and the encryption key can decrypt them. Admin-only commands control bot and media operations.

## Notes
- Additional bots must be invited to the server and granted Connect/Speak permissions.
- Uploads are limited by Discord's attachment size and `MAX_UPLOAD_MB`.
- Playback starts independently per bot; exact sample-level synchronization is not guaranteed.
- Slash commands may take a short time to appear after the first global sync.
