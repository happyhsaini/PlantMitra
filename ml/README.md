# PlantNet streaming experiment

This workflow reads individual rows from `mikehemberger/plantnet300K` with Hugging Face streaming. It does not download or extract the Zenodo ZIP or materialize the complete dataset. The first command is only a five-image smoke test; training is a separate explicit `--train` action.

## Run in Google Colab

Upload/clone the project, then run:

```bash
pip install -r ml/requirements.txt
python -m ml.dataset.stream_plantnet
```

The smoke test prints the actual columns and label IDs, resolves those IDs through the small official Pl@ntNet species-name mapping, streams five training examples, prints their scientific names, opens one image, and updates `ml/dataset/classes.json` with the mapping plus only exact matches from the medicinal target candidates. An absent species is never renamed or replaced. Set `--no-display` on a headless runtime. Only the small taxonomy JSON is cached in addition to Hugging Face's streamed shards; no image archive is downloaded.

The installed Hugging Face `datasets` package and network connection are required. The repository's restricted local shell may not be able to reach Hugging Face; Colab or another online Python runtime can run the same command.

## Training (explicit opt-in)

Only after the smoke test succeeds and `ml/dataset/classes.json` contains ten actual medicinal class labels:

```bash
python -m ml.training.train --train --num-classes 10 --max-images-per-class 100
```

Without `--train`, the training script runs the five-image smoke test only. With `--train`, it repeats that test, refuses to proceed if ten exact classes are unavailable, then streams at most 100 training images per class and a separate validation cap. Images are decoded on demand; the full dataset is not saved. A small MobileNetV3-Small model and its class mapping are written to `ml/artifacts/` only after training finishes.

The current project medicinal list has several species that may not occur as exact labels in this dataset. The existing dataset audit found only *Phyllanthus emblica* among its exact medicinal target names; consequently it does not currently meet the ten-class training requirement. Do not train or claim a ten-species model until the streaming inspection confirms enough actual labels and images.

## Dataset

Dataset: [mikehemberger/plantnet300K](https://huggingface.co/datasets/mikehemberger/plantnet300K). Cite the Pl@ntNet-300K paper and check image-level licensing before redistributing images or model weights.
