import os
try:
    import ConfigParser
except ImportError:
    try:
        import configparser as ConfigParser
    except ImportError:
        pass

def default_config():
    default_path = "/goodreads.cfg"
    if os.path.exists(os.path.dirname(__file__) + default_path):
        config = ConfigParser.ConfigParser()
        config.read(os.path.dirname(__file__) + default_path)
        return config
    else:
        return None

def _read_config(filename=None):
    if filename:
        config = ConfigParser.ConfigParser()
        config.read(filename)
    elif default_config:
        config = default_config()
    return config

def get_config(section, filename=None):
    config = _read_config(filename)
    if config:
        try:
            return dict(config.items(section))
        except Exception as e:
            pass
    raise Exception("Please provide a configuration file with a section named {0}".format(section))
