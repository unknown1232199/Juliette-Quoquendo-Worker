# Wire the RVC stage into the supplied Loquendo Cog

The optional processing helper is in `rvc_stage.py`. Apply the following
small changes to the active `loquendo.py` Cog. This deliberately avoids
rewriting the bot or changing its existing commands.

## 1. Import the helper

Place next to the other imports:

```python
try:
    import rvc_stage
except ImportError:
    rvc_stage = None
```

## 2. Add one method to the Cog

Place inside `class Loquendo`:

```python
    async def process_tts_audio(self, audio):
        if rvc_stage is None:
            return audio
        return await rvc_stage.process_tts_audio(audio, self.config)
```

## 3. Pass every generated audio result through the stage

Inside `synthesize()`, replace each of its three successful `return audio`
statements with:

```python
            return await self.process_tts_audio(audio)
```

There are three successful generation paths in the supplied file:
Quoquendo adapter, local CLI, and HTTP TTS provider. Make the replacement in
all three branches. Do not change returns in other methods.

Because both manual `/tts` and automatic channel reading call
`synthesize()`, this single hook covers both playback paths. The RVC stage
returns the original audio unchanged when disabled or when no model is
selected.

## 4. Config keys

The Cog's existing `loquendo_config.json` can hold these optional keys:

- `rvc_enabled`: boolean, default false
- `rvc_model`: model ID, default empty
- `rvc_fallback`: boolean, default true

The first catalog ID is
`kasane-teto-synthv-rvc-v2`. It is only a catalog entry; the weights must be
installed by the external inference service. Set `JULIETTE_RVC_URL` to that
service's HTTPS conversion endpoint.

## Important

This patch wires audio processing, not the Discord control surface. Do not
enable RVC until a real external service and model are installed and tested.
The existing `/fakevoice` command currently configures a TTS provider URL;
it is not yet a model manager. The next command-layer change should add
`/fakevoice status`, provider selection, RVC enable/disable, and model
selection while retaining the existing `/provider` command as a compatible
alias.
