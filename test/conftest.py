import pytest

def pytest_addoption(parser):
    parser.addoption('--online', action='store', default='both',
                     choices=["both", "spiritdc", "spiritdcb"],
                     help='Select test class')
    parser.addoption('--logfile', action='store', default='of_regression.log',
                     help='Select log file')


@pytest.fixture(scope='session')
def online(request):
    online_value = request.config.option.online
    if online_value is None:
        return "both"
    return online_value

@pytest.fixture(scope='session')
def logfile(request):
    logfile_value = request.config.option.logfile
    if logfile_value is None:
        return "of_regression.log"
    return logfile_value
