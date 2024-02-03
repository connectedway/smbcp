import pytest

def pytest_addoption(parser):
    parser.addoption('--logfile', action='store', default='of_regression.log',
                     help='Select log file')


@pytest.fixture(scope='session')
def logfile(request):
    logfile_value = request.config.option.logfile
    if logfile_value is None:
        return "of_regression.log"
    return logfile_value
