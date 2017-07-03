from fewerror.thatsnotmybot import ThatsNotMyBot


def test_validate():
    ThatsNotMyBot()

def test_argparse():
    ThatsNotMyBot().main([])