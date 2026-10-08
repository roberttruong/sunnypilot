#!/usr/bin/env python3
"""
Subaru longitudinal maneuver report: what was sent to the car (Cruise_Throttle, Cruise_RPM, Brake_Pressure),
the road grade estimate, and how the car responded, optionally overlaying two routes (e.g. baseline vs new tables).

  python openpilot/tools/longitudinal_maneuvers/subaru_report.py <route> [<compare route>] [--labels baseline new]
"""
import argparse
import base64
import io
import webbrowser
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from opendbc.can import CANParser
from opendbc.car.subaru.values import DBC
from openpilot.common.utils import tabulate
from openpilot.tools.lib.logreader import LogReader
from openpilot.tools.longitudinal_maneuvers.generate_report import get_maneuvers

COLORS = ["#2a78d6", "#eb6834"]  # first route, second route
HILL_RC = 1.0  # s, same filter as carstate


def parse_run(msgs, dbc):
  """Time series for one maneuver run, all on seconds since the start of the run."""
  sent = CANParser(dbc, [("ES_Distance", 20), ("ES_Status", 20), ("ES_Brake", 20)], 0)
  pt = CANParser(dbc, [("G_Sensor", 50), ("Throttle", 100)], 0)
  t0 = msgs[0].logMonoTime
  out = defaultdict(list)
  hill = 0.
  a_ego = 0.
  t_prev = None

  for m in msgs:
    t = (m.logMonoTime - t0) * 1e-9
    w = m.which()
    if w == 'carState':
      a_ego = m.carState.aEgo
      out['t_cs'].append(t)
      out['v'].append(m.carState.vEgo)
      out['a'].append(a_ego)
    elif w == 'longitudinalPlan':
      out['t_plan'].append(t)
      out['a_target'].append(m.longitudinalPlan.aTarget)
    elif w == 'sendcan':
      if sent.update([(m.logMonoTime, [(c.address, c.dat, c.src) for c in m.sendcan])]):
        out['t_sent'].append(t)
        out['throttle'].append(sent.vl['ES_Distance']['Cruise_Throttle'])
        out['rpm_cmd'].append(sent.vl['ES_Status']['Cruise_RPM'])
        out['brake'].append(sent.vl['ES_Brake']['Brake_Pressure'])
    elif w == 'can':
      if 0x13b in pt.update([(m.logMonoTime, [(c.address, c.dat, c.src) for c in m.can])]):
        dt = 0.02 if t_prev is None else max(t - t_prev, 1e-3)
        t_prev = t
        hill += dt / (HILL_RC + dt) * ((pt.vl['G_Sensor']['Longitudinal'] - a_ego) - hill)
        out['t_pt'].append(t)
        out['hill'].append(hill)
        out['engine_rpm'].append(pt.vl['Throttle']['Engine_RPM'])

  return {k: np.array(v) for k, v in out.items()}


def run_metrics(r):
  """Time for aEgo to cross the initial target, overshoot past it, and speed drift over the run."""
  metrics = {'cross_time': None, 'overshoot': None, 'speed_drift': None}
  if len(r.get('a_target', [])) == 0 or len(r.get('a', [])) == 0:
    return metrics
  target = r['a_target'][0]
  a, t = r['a'], r['t_cs']
  if abs(target) > 0.05:
    crossed = np.flatnonzero((a >= target) if target > 0 else (a <= target))
    if len(crossed):
      metrics['cross_time'] = round(float(t[crossed[0]]), 2)
    metrics['overshoot'] = round(float(np.max(a - target) if target > 0 else np.max(target - a)), 2)
  else:
    metrics['speed_drift'] = round(float(r['v'][-1] - r['v'][0]), 2)
  return metrics


def plot_run(runs, labels):
  fig, ax = plt.subplots(5, 1, figsize=(10, 12), sharex=True, gridspec_kw={'height_ratios': [3, 2, 2, 2, 1.5]})
  for r, label, color in zip(runs, labels, COLORS, strict=False):
    if r is None:
      continue
    ax[0].plot(r['t_cs'], r['a'], color=color, lw=2, label=f'{label}: aEgo')
    ax[0].plot(r['t_plan'], r['a_target'], color=color, lw=1.2, ls='--', label=f'{label}: aTarget')
    ax[1].plot(r['t_sent'], r['throttle'], color=color, lw=2, label=label)
    ax[2].plot(r['t_sent'], r['rpm_cmd'], color=color, lw=2, label=f'{label}: Cruise_RPM sent')
    ax[2].plot(r['t_pt'], r['engine_rpm'], color=color, lw=1, alpha=0.6, label=f'{label}: Engine_RPM')
    ax[3].plot(r['t_sent'], r['brake'], color=color, lw=2, label=label)
    ax[4].plot(r['t_pt'], r['hill'], color=color, lw=2, label=label)
  ax[1].axhline(3400, color='#52514e', lw=1, ls=':')
  labels_y = ['accel (m/s²)', 'Cruise_Throttle', 'RPM', 'Brake_Pressure', 'hill (m/s²)']
  for a, lab in zip(ax, labels_y, strict=True):
    a.set_ylabel(lab)
    a.grid(True, color='#ebeae5')
    a.legend(loc='upper right', fontsize=8)
  ax[-1].set_xlabel('Time (s)')
  fig.tight_layout()
  buffer = io.BytesIO()
  fig.savefig(buffer, format='webp')
  plt.close(fig)
  return f"<img src='data:image/webp;base64,{base64.b64encode(buffer.getvalue()).decode()}' style='width:100%; max-width:900px;'>\n"


def main():
  parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
  parser.add_argument('routes', nargs='+', help='one or two route names')
  parser.add_argument('--labels', nargs='+')
  args = parser.parse_args()
  assert len(args.routes) <= 2, 'at most two routes'
  labels = args.labels or args.routes

  route_maneuvers, platform = [], None
  for route in args.routes:
    lr = LogReader(route)
    platform = lr.first('carParams').carFingerprint
    dbc = DBC[platform]['pt']
    maneuvers = {desc: [parse_run(run, dbc) for run in runs if len(run)] for desc, runs in get_maneuvers(lr)}
    route_maneuvers.append(maneuvers)
    print(f'{route}: {platform}, {len(maneuvers)} maneuvers')

  descriptions = list(dict.fromkeys(d for m in route_maneuvers for d in m))
  builder = ["<style>summary { cursor: pointer; } td, th { padding: 6px; }</style>\n",
             f"<h1>Subaru longitudinal maneuver report</h1><h3>{platform}</h3>\n"]
  builder += [f"<h3>{label}: {route}</h3>\n" for label, route in zip(labels, args.routes, strict=False)]
  summary_rows = []

  body = []
  for desc in descriptions:
    body.append(f"<hr><h2>{desc}</h2>\n")
    n_runs = max(len(m.get(desc, [])) for m in route_maneuvers)
    for i in range(n_runs):
      runs = [m[desc][i] if i < len(m.get(desc, [])) else None for m in route_maneuvers]
      body.append(f"<details {'open' if i == 0 else ''}><summary><h3 style='display:inline-block'>Run #{i + 1}</h3></summary>\n")
      body.append(plot_run(runs, labels))
      body.append("</details>\n")
      for label, r in zip(labels, runs, strict=False):
        if r is not None:
          mt = run_metrics(r)
          summary_rows.append([desc, label, i + 1, mt['cross_time'], mt['overshoot'], mt['speed_drift']])

  builder.append("<h2>Summary</h2>\n")
  builder.append(tabulate(summary_rows, headers=['maneuver', 'route', 'run', 'time to target (s)', 'overshoot (m/s²)', 'speed drift (m/s)'],
                          tablefmt='html', numalign='left') + '\n')
  builder += body

  out_dir = Path(__file__).resolve().parent / 'longitudinal_reports'
  out_dir.mkdir(exist_ok=True)
  out_fn = out_dir / f"subaru_{'_vs_'.join(r.replace('/', '_') for r in args.routes)}.html"
  out_fn.write_text(''.join(builder))
  print(f'Report written to {out_fn}')
  webbrowser.open_new_tab(str(out_fn))


if __name__ == '__main__':
  main()
