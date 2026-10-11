# Local model artifacts

Model weights are excluded from Git. The original `graduation.zip` contains:

| Artifact | Purpose |
| --- | --- |
| `Envelope_box_detection.pt` | Parcel/envelope detection |
| `info.pt` | Information-region detection |
| `trocr-vietnamese-final/` | Vietnamese handwriting recognition; keep config/tokenizer and weights together |
| `box_detect.pt`, `hand_detect.pt`, `persondetect.pt`, `best.pt` | Camera-related detection variants |
| `ocrweight.pt` | Scale-image detection |

The archive also contains an old Git history with large objects. Restore only the model members using the script below; the old Git history is not needed.

From the repository root, first inspect the restoration plan:

```powershell
python scripts/restore_local_artifacts.py --archive "..\Đồ án phần data code\Huy ANh_Pricing_ Handwriting Recognition\graduation.zip"
```

To restore after viewing the plan:

```powershell
python scripts/restore_local_artifacts.py --archive "..\Đồ án phần data code\Huy ANh_Pricing_ Handwriting Recognition\graduation.zip" --extract
```

Use `--kind videos` to inspect or restore the original demo videos into the Git-ignored `media/videos/` folder. Existing files are skipped. A clone downloaded from GitHub will not have the original archive; use model files supplied by the project owner in the paths above. No public model download link has been supplied.
