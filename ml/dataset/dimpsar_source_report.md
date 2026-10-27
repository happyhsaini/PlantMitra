# DIMPSAR Mendeley V3 Source Investigation

## Summary

The research paper describes species-named folders, which suggests that the original data is organized by plant species. However, the public Mendeley V3 record's rendered page exposes a **Download All** control and an empty `Files` section; it does not expose individual file names, folder entries, sizes, or per-class download links. The Mendeley Data API documents file and folder listing plus file-level download URLs, but this investigation could not retrieve the record's actual file listing. Therefore, it is **not verified** whether the seven classes can be downloaded separately, and the exact archive/download size is **unknown**. No data was downloaded.

## Requested Fields

| Field | Verified result |
|---|---|
| `source` | [Mendeley Data: Indian Medicinal Leaves Image Datasets](https://data.mendeley.com/datasets/748f8jkphb/3), the original research dataset record. |
| `version` | V3, DOI `10.17632/748f8jkphb.3`, published 5 May 2023. |
| `license` | CC BY 4.0, as stated on the Mendeley record. Attribution is required; provide creator credit, a link to the license, and indicate changes. See [CC BY 4.0 deed](https://creativecommons.org/licenses/by/4.0/). |
| `total_size` | **Not discoverable from the accessible public record.** The page has no visible file entries or sizes. Do not infer this from the Hugging Face mirror, since it is a transformed Parquet copy rather than the original Mendeley payload. |
| `target_classes` | Aloevera, Amla, Ashwagandha, Brahmi, Mint, Neem, Tulasi. The research paper describes 40 whole-plant classes and species-named folders, but the accessible paper text does not enumerate and independently verify these seven folder names in V3. These names are present in the Project-AgML Hugging Face processed mirror; that does not establish Mendeley file/folder IDs. |
| `class_access_method` | The paper says images are compiled into separate folders named for plant species. The Mendeley public page does not reveal whether those folders are separately downloadable or whether they are nested inside one archive. The API supports listing public dataset files/folders and file-level download URLs in principle, but the actual V3 listing was not obtained in this investigation. |
| `individual_download_available` | **Unverified.** Mendeley documents public folder/file endpoints, but no target-class folder IDs, individual file names, or direct URLs for this record could be verified. The web record itself exposes only Download All. |
| `recommended_training_source` | Do not download the Mendeley record yet. First obtain its actual V3 file/folder listing and byte sizes through an accessible Mendeley API response or record owner. If it proves to be a single archive only, obtain the exact size and explicit user approval before any download. Do not substitute the Hugging Face shard as though it were the original folder dataset. |

## Findings

### Record and research organization

The Mendeley V3 page confirms the title, version, DOI, authors (Pushpa B R and Shobha Rani), and CC BY 4.0 license. The associated paper reports a whole-plant dataset of 5,900 images across 40 species, as well as a separate medicinal-leaf dataset. Its data-description text says that collected images are compiled into separate folders whose names are the plant species. This is evidence of the research organization, not proof that Mendeley exposes each folder as an independently downloadable object.

### Files, size, formats, and smallest download

- Visible Mendeley page control: **Download All**.
- Visible file listing: none; the `Files` heading has no entries in the accessible page extraction.
- Exact V3 archive/file names and sizes: **not verified**.
- Whether there is a ZIP, 7z, RAR, or another archive: **not verified**.
- Whether target-class folders can be fetched individually: **not verified**.
- Original image extensions (JPG/JPEG/PNG): **not verified from the Mendeley V3 file listing**. The paper discusses image data but the accessible description does not provide a file-extension inventory.
- Smallest legitimate download that contains all seven classes: **cannot be determined from current evidence**. No dataset bytes were fetched.

The Mendeley Data API documentation describes public dataset file/folder metadata and a file-level endpoint that can return metadata such as filename, folder ID, content type, size, and a download URL. That means class-specific acquisition may be technically possible if the V3 record stores species folders/files as separate objects. The API's existence alone does not verify that this particular record is arranged that way. The documented API requires authentication, and an anonymous metadata lookup was not available in this investigation.

### License and attribution

The Mendeley record states **CC BY 4.0**. Reuse must retain appropriate creator attribution, include the license link, and identify modifications. Recommended dataset attribution:

> Pushpa, B. R., & Rani, S. (2023). *Indian Medicinal Leaves Image Datasets* (Version 3) [Data set]. Mendeley Data. https://doi.org/10.17632/748f8jkphb.3

The associated research article is Pushpa, B. R., & Rani, S. (2023), “DIMPSAR: Dataset for Indian medicinal plant species analysis and recognition,” *Data in Brief*, 49, 109388. Preserve both dataset and paper citations in model/data documentation. If images are resized, augmented, or otherwise transformed, state that changes were made.

## Sources

- [Mendeley Data V3 record](https://data.mendeley.com/datasets/748f8jkphb/3)
- [DIMPSAR research paper (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10375553/)
- [Mendeley Data API documentation](https://data.mendeley.com/api/docs/)
- [Creative Commons Attribution 4.0 deed](https://creativecommons.org/licenses/by/4.0/)
- [Project-AgML Hugging Face mirror](https://huggingface.co/datasets/Project-AgML/DIMPSAR_medicinal_plant_classification) (used only as a processed-mirror reference for labels; not treated as the original file listing)

## Stop Condition

No dataset files, archive, or images were downloaded. No training was run. Because the Mendeley V3 file manifest and exact size remain inaccessible, this report does **not** conclude that Download All is the only option; it also cannot verify class-specific downloads. Further acquisition should wait until the record's manifest can be inspected without downloading the data.
