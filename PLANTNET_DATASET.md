# PlantNet-300K dataset inventory

Checked 2 October 2026 from the official Zenodo records and the v2 metadata CSV. No image archive was downloaded into this repository.

## Dataset versions

| Release | Images | Species | Train | Validation | Test | Archive |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| v1.1 (the supplied URL) | 306,146 | 1,081 | 243,916 | 31,118 | 31,112 | 31.7 GB |
| v2 (organ-labelled metadata) | 306,087 | 1,000 | 243,866 | 31,115 | 31,106 | 41.8 GB |

Sources: [Zenodo v1.1](https://zenodo.org/records/5645731), [Zenodo v2](https://zenodo.org/records/10419064).

## v2 organ labels

| Organ label | Images |
| --- | ---: |
| flower | 176,501 |
| leaf | 110,760 |
| fruit | 11,275 |
| habit | 4,442 |
| bark | 2,076 |
| other | 993 |
| branch | 37 |
| scan | 2 |
| none | 1 |

The v2 metadata also provides species IDs, observation IDs, author, license, split, and image hashes. The species metadata provides scientific name, genus, family, author, and IUCN status.

## Exact target-label check (v2)

Only **Phyllanthus emblica** (Amla) is present among the medicinal target species requested in the project brief: 27 images total (21 train, 3 validation, 3 test; organ labels: 16 leaf, 10 fruit, 1 other). The other checked targets are not present as exact classes: Azadirachta indica, Ocimum tenuiflorum, Aloe vera, Withania somnifera, Moringa oleifera, Bacopa monnieri, Centella asiatica, Mentha genus, and Curcuma longa.

Do not infer/substitute labels for absent species. Twenty-seven Amla images are not enough to make a dependable medicinal-plant classifier. Select either a broader all-species PlantNet classifier or a different medicinal-plant dataset before training.

## Training and licensing notes

The v2 archive is about 41.8 GB; the v1.1 archive is about 31.7 GB. Stream or selectively download only after choosing the model scope; do not commit image archives to this application. The checked local environment has no PyTorch/CUDA setup, so model training should run in a suitable GPU notebook (for example, Google Colab), not be represented as completed here.

The v2 CSV lists 305,614 `cc-by-sa`, 376 `cc-by-nc`, and 97 `cc-by-nc-sa` images. Check image-level licenses and attribution obligations before redistributing data or deploying weights commercially.

## Observation organ stickers

The app's observation upload lets the user select the pictured organ (leaf, flower, fruit, bark, whole-plant habit, branch, seed, bud, other, or aerial picture). The observation card and its details display that selection as a sticker. This is user-supplied metadata, not an AI organ prediction.
