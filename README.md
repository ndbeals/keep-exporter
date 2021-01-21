# Keep-Exporter
A command line utility to export Google Keep notes to markdown files with metadata stored as a frontmatter header. 

Supports exporting:
 - Simple notes
 - List notes
 - Images and Drawings
 - Audio clips
 - Link annotations

## Usage
If you do not supply a username or password before running it, you will be prompted to input them.
```
Usage: keep_export [OPTIONS]
Options:
  -u, --user TEXT            Google account email (prompt if empty)  [env var: GKEEP_USER; required]
  -p, --password TEXT        Google account password (prompt if empty)  [env var: GKEEP_PASSWORD; required]
  -d, --directory DIRECTORY  Output directory for exported notes  [default: ./gkeep-export]
  --header / --no-header     Choose to include or exclude the frontmatter header  [default: True]
  -h, --help                 Show this message and exit.
```

### Notes
If you are using 2 Factor Authentication (2FA) for your google account, you will need to generate an app password for keep. You can do so on your [Google account management page.](https://myaccount.google.com/apppasswords)


## Installation
There are many ways to install this, easiest are through pip or the releases page.

### Pip
The easiest way is with [pip from PyPi](https://pypi.org/project/keep-exporter/)
```
pip3 install keep-exporter
```

### Download the Wheel
Download the wheel from the [releases page](https://github.com/ndbeals/keep-exporter/releases) and then install with pip:
```
pip install keep_exporter*.whl
```

### Building
#### Download or git clone
 1. Clone the repository `https://github.com/ndbeals/keep-exporter` or download from the [releases page](https://github.com/ndbeals/keep-exporter/releases) and extract the source code.
 2. `cd` into the extracted directory
 3. With [poetry](https://python-poetry.org/) installed, run `poetry install` in the project root directory
 4. `poetry build` will build the installable wheel
 5. `cd dist` then run `pip3 install <keep-exporter-file.whl>`


## Troubleshooting
Some users have had issues with the requests library detailed in [this issue](https://github.com/ndbeals/keep-exporter/issues/1) when using `pipx`. The solution is to change the requests library version.
```
pipx install keep-exporter 
pipx inject keep-exporter requests===2.23.0
```
