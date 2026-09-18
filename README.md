# Video Clipper

**Extract and concatenate video segments from a source file using ffmpeg**.    
*dedicated to Sophie*

*This is my first try of developing a (small) program using exclusively **AI** - here `opencode` and `qwen3.5`

It took  some trial/error, the most difficult part (for qwen) was finding the correct `ffmpeg` arguments    
The only correction I did is improving the file chooser in the streamlit GUI version (using *EURIA* this time), and in this README file.

That was a fun trial, there is certainly potential here, however, I am not sure I will use it further on...


## Requirements

- Python 3.6+
- `ffmpeg` / `ffprobe` installed and on PATH

## Usage

```bash
python3 video_clipper.py
```
There are two usages:

### interactive mode 
The tool will:

1. Ask for the input video file path
2. Let you add multiple segments by specifying start/end timestamps
3. Generate a concatenated output video

### CLI mode

```bash
python3 video_clipper.py [-h] [-o OUTPUT] [--debug] input [segments ...]
```
try 
```bash
python3 video_clipper.py -h
```
for details
## Timestamp Formats

Accepts:
- `MM:SS` (e.g., `02:30`)
- `HH:MM:SS` (e.g., `00:02:30`)
- With fractional seconds (e.g., `02:30.500`)
- Plain seconds (e.g., `150`)

## Examples

```
Enter path to input video file: my_video.mp4

--- Segment #1 ---
  Start time (or 'done' to finish): 00:30
  End time: 01:45

--- Segment #2 ---
  Start time (or 'done' to finish): 03:00
  End time: 04:10

  Start time (or 'done' to finish): done

Output file path [my_video_clipped.mp4]:
```

## How It Works

- Segments are extracted using `ffmpeg -c copy` (stream copy, fast, no re-encoding)
- Segments are concatenated via ffmpeg's concat demuxer
- If stream copy fails (codec mismatch), it falls back to re-encoding with `libx264`
- Temporary files are cleaned up automatically

## Installation
- fetch the code
```bash
 git clone https://github.com/delsuc/video_clipper.git
 cd video_clipper/
```
### test file
If you want to get the small video test file, it is handled by LFS, so  `git-lfs` has to be installed on your machine.

Then you have to replace the video file pointer brough by `git clone` with the real file:
```bash
 git lfs install             # activate lfs in this project
 git lfs fetch --all         # synchronise
 git lfs checkout            # and checkout
```

# Companion program : stream_clipper

`stream_clipper.py` is a graphical interface for `video_clipper.py` *(in French)*

just install streamlit ( https://streamlit.io/ ) 

I usually use `uv` with a local virtual interface :
```bash
uv venv
source .venv/bin/activate
uv pip install streamlit
```

to launch, do
```bash
streamlit run stream_clipper.py
```
a browser page should open with the GUI

closing the terminal or `^C` to finish.


