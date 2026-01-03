## Installation

Kiln supports two patterns:

- **Conda (recommended)**: one env containing UI + USD + Genesis dependencies.
- **Pip**: install the UI (and optionally USD/Genesis extras).

### Conda (recommended)

Create the dev environment:

```bash
conda env create -f environment.yml
conda activate kiln-dev
```

Update an existing env after `environment.yml` changes:

```bash
conda env update -n kiln-dev -f environment.yml --prune
conda activate kiln-dev
```

Run the UI:

```bash
python kiln.py
```

### Pip

Install the base UI:

```bash
python -m pip install -e .
```

Optional extras:

- USD support (UI scene creation/preview):

```bash
python -m pip install -e ".[usd]"
```

- Genesis backend:
  - Install PyTorch first (CPU or CUDA, per Genesis docs)
  - Then install the Genesis extra:

```bash
python -m pip install -e ".[sim]"
```

- Documentation site:

```bash
python -m pip install -e ".[docs]"
mkdocs serve
```



