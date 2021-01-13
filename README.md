# Keep-Exporter
A command line utility to export Google Keep notes to markdown files with metadata stored as a frontmatter header. 

## Installation
There are many ways to install this, easiest are through pip or the releases page.

### Pip
The easiest way is with [pip from PyPi](https://pypi.org/project/keep-exporter/)
```
pip3 install keep-exporter
```

### Download or git clone
 1. Clone the repository `https://github.com/ndbeals/keep-exporter` or download from the [releases page](https://github.com/ndbeals/keep-exporter/releases) and extract the source code.
 2. `cd` into the directory
 3. With poetry installed, run `poetry install` in the project root directory
 4. `poetry build` will build the installable wheel
 5. `cd dist` then run `pip3 install <keep-exporter-file.whl>`


## Usage
```
keep_export [OPTIONS]
Options:
  -d, --directory TEXT  Output directory for exported notes
  -u, --user TEXT       Google account email (environment variable 'GKEEP_USER')
  -p, --password TEXT   Google account password (environment variable 'GKEEP_PASSWORD')
```