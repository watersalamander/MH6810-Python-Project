# Data (not included in this repository)

The dataset comes from the DrivenData competition
[Richter's Predictor: Modeling Earthquake Damage](https://www.drivendata.org/competitions/57/nepal-earthquake/).
Its rules do not allow participants to redistribute the data, so the CSVs are
git-ignored and must be downloaded by each person.

1. Create a free DrivenData account and join the competition.
2. Open the competition's **Data download** page and download the three files.
3. Place them in this folder, keeping the original names:

```
data/
  train_values.csv    (about 23 MB, 260,601 rows x 39 columns)
  train_labels.csv    (about 2 MB,  260,601 rows x 2 columns)
  test_values.csv     (about 8 MB,   86,868 rows x 39 columns)
```

Then run `python -m src.run_all` from the project root.
