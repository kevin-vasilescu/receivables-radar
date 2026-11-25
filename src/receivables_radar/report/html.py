'''Self-contained HTML report.'''

from __future__ import annotations

from typing import TYPE_CHECKING

from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup

from receivables_radar.report.charts import aging_bar, forecast_bars
from receivables_radar.report.markdown import money, num, pct

if TYPE_CHECKING:
    from receivables_radar.analysis import AnalysisResult

_ENV = Environment(
    loader=PackageLoader('receivables_radar', 'report/templates'),
    autoescape=select_autoescape(['html', 'j2'], default_for_string=True, default=True),
)
_ENV.filters.update({'money': money, 'pct': pct, 'num': num})


def render_html(res: AnalysisResult) -> str:
    '''Render the report as one HTML document with inline CSS and SVG.

    Args:
        res: Analysis result.

    Returns:
        HTML text with no external references.
    '''
    names = [s.name for s in res.config.scenarios]
    forecasts = {n: res.forecast(n) for n in names}
    base = forecasts[names[0]]
    rows = []
    for i in range(len(base)):
        first = base.iloc[i]
        label = str(first['week'])
        if first['week_start'] is not None:
            label = f'{label} ({first["week_start"]:%Y-%m-%d})'
        rows.append({'label': label, 'values': [forecasts[n].iloc[i]['expected_cash'] for n in names]})
    aging = res.aging()
    return _ENV.get_template('report.html.j2').render(
        as_of=res.as_of.isoformat(),
        currency=res.config.currency_code,
        kpis=res.kpis(),
        risk=res.uncollectable_risk(),
        warnings=res.warnings,
        invoice_count=res.invoice_count,
        payment_count=res.payment_count,
        aging=aging.itertuples(),
        top=res.top_customers().itertuples(),
        tiers=res.risk_tiers().itertuples(),
        scenario_names=names,
        forecast_rows=rows,
        weeks=res.config.forecast_weeks,
        worklist=res.worklist().head(25).itertuples(),
        aging_svg=Markup(aging_bar(aging)),
        forecast_svg=Markup(forecast_bars(base)),
    )
