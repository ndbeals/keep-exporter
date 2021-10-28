# Keep-Exporter
[
![PyPi](https://img.shields.io/pypi/v/keep-exporter)
![PyPi](https://img.shields.io/pypi/pyversions/keep-exporter)
![PyPi](https://img.shields.io/pypi/l/keep-exporter)
](https://pypi.org/project/keep-exporter/)

A command line utility to export Google Keep notes to markdown files with metadata stored as a frontmatter header. 

## Features

 * Exports all note types (List and Note)
 * Exports all media attached to notes
   * Audio, drawings, attached images, etc
 * Sync Keep to directory (keeps directory looking exactly the same as Google Keep)
 * Customizable date format
   * Easy ISO8601 via `--iso8601`
 * Password or token based authentication
   * Store your login token to config file with `keep_export savetoken`
 * Note metadata header in yaml frontmatter format


## Usage
If you do not supply a username or password before running it, you will be prompted to input them.
```
Usage: keep_export [OPTIONS] COMMAND [ARGS]...

Options:
  --config FILE                   Read configuration from FILE.  [default: /home/nate/.config/keep-exporter]
  -u, --user TEXT                 Google account email (prompt if empty)  [env var: GKEEP_USER;required]
  -p, --password TEXT             Google account password (prompt if empty). Either this or token is required.  [env var: GKEEP_PASSWORD]
  -t, --token TEXT                Google account token from prior run. Either this or password is required.
  -d, --directory DIRECTORY       Output directory for exported notes  [default: ./gkeep-export]
  --header / --no-header          Choose to include or exclude the frontmatter header  [default: header]
  --delete-local / --no-delete-local
                                  Choose to delete or leave as-is any notes that exist locally but not in Google Keep  [default: no-delete-local]
  --rename-local / --no-rename-local
                                  Choose to rename or leave as-is any notes that change titles in Google Keep  [default: no-rename-local]
  --date-format TEXT              Date format to prefix the note filenames. Reflects the created date of the note. uses strftime()  [default: %Y-%m-%d]
  --iso8601                       Format dates in ISO8601 format.
  --skip-existing-media / --no-skip-existing-media
                                  Skip existing media if it appears unchanged from the local copy.  [default: skip-existing-media]
  -h, --help                      Show this message and exit.

Commands:
  savetoken  Saves the master token to your configuration file.
```

### Notes
If you are using 2 Factor Authentication (2FA) for your google account, you will need to generate an app password for keep. You can do so on your [Google account management page.](https://myaccount.google.com/apppasswords)


## Installation
There are many ways to install this, easiest is through pip or the releases page.

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
