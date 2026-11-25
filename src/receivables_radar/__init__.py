'''Receivables Radar: aging, DSO, risk, cash forecast and collections worklist.'''

from receivables_radar.analysis import AnalysisResult, analyze
from receivables_radar.config import Config, Scenario
from receivables_radar.io import load_invoices, load_payments
from receivables_radar.models import DataError

__version__ = '0.1.0'
__all__ = ['AnalysisResult', 'Config', 'DataError', 'Scenario', 'analyze', 'load_invoices', 'load_payments']
