"""Reproduce the train/test split and linear calibration in the supplied notebook."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error

HERE = Path(__file__).resolve().parent
TEST_DISTANCES = [11, 21, 31, 41, 51, 61, 71, 81, 91]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook', type=Path, default=HERE / 'data.xlsx')
    parser.add_argument('--plot', action='store_true')
    args = parser.parse_args()
    cal = pd.read_excel(args.workbook, sheet_name='Calibration')
    sensors = ['CB1_cm', 'CB2_cm', 'CB3_cm']
    cols = ['Actual_cm', *sensors]
    cal[cols] = cal[cols].apply(pd.to_numeric, errors='coerce')
    cal = cal.dropna(subset=cols)
    train = cal[~cal['Actual_cm'].isin(TEST_DISTANCES)]
    test = cal[cal['Actual_cm'].isin(TEST_DISTANCES)]
    if train.empty or test.empty:
        raise ValueError('The workbook must contain both training and held-out reference distances.')
    rows = []
    for sensor in sensors:
        model = LinearRegression().fit(train[[sensor]], train['Actual_cm'])
        prediction = model.predict(test[[sensor]])
        actual = test['Actual_cm']
        before = mean_absolute_error(actual, test[sensor])
        after = mean_absolute_error(actual, prediction)
        rows.append({
            'sensor': sensor.removesuffix('_cm'),
            'coefficient': float(model.coef_[0]), 'intercept': float(model.intercept_),
            'mae_before_cm': before, 'mae_after_cm': after,
            'rmse_after_cm': float(np.sqrt(np.mean((actual - prediction) ** 2))),
            'mape_after_pct': mean_absolute_percentage_error(actual, prediction) * 100,
            'mae_improvement_pct': (before - after) / before * 100,
        })
    result = pd.DataFrame(rows)
    result.to_csv(HERE / 'calibration_results.csv', index=False, float_format='%.6f')
    report = {'source_workbook': 'data.xlsx', 'sheet': 'Calibration',
              'train_samples': len(train), 'test_samples': len(test),
              'held_out_distances_cm': TEST_DISTANCES, 'sensors': rows}
    (HERE / 'calibration_results.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'Train samples: {len(train)}; test samples: {len(test)}')
    print(result.round(4).to_string(index=False))
    if args.plot:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, axis = plt.subplots(figsize=(8, 4.5), layout='constrained')
        x = np.arange(len(result))
        before_bars = axis.bar(x - 0.18, result['mae_before_cm'], 0.36, label='Before calibration', color='#7c8ca5')
        after_bars = axis.bar(x + 0.18, result['mae_after_cm'], 0.36, label='After calibration', color='#147d92')
        axis.bar_label(before_bars, fmt='%.3f', padding=3)
        axis.bar_label(after_bars, fmt='%.3f', padding=3)
        axis.set_xticks(x, result['sensor'])
        axis.set_ylabel('Mean absolute error (cm)')
        axis.set_title(f'ESP32 sensor calibration | {len(test):,} held-out measurements')
        axis.set_ylim(0, result['mae_before_cm'].max() * 1.3)
        axis.legend(frameon=False)
        axis.spines[['top', 'right']].set_visible(False)
        fig.savefig(HERE.parents[1] / 'media/sensor-calibration.png', dpi=160)
        plt.close(fig)


if __name__ == '__main__':
    main()
