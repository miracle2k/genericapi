# simple test runner wrapper (useful for test debugging in IDEs)
if __name__ == "__main__":
    from py.test import cmdline
    import sys
    sys.exit(cmdline.main(['.'] + sys.argv[1:]))