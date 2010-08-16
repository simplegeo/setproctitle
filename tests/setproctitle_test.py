"""setproctitle module unit test.

Use nosetests to run this test suite.

Copyright (c) 2009-2010 Daniele Varrazzo <daniele.varrazzo@gmail.com>
"""

import os
import re
import sys
import shutil
import tempfile
import unittest
from subprocess import Popen, PIPE, STDOUT

IS_PY3K = sys.version_info[0] == 3

try:
    from nose.plugins.skip import SkipTest
except ImportError:
    try:
        from unittest import SkipTest
    except ImportError:
        class SkipTest(Exception):
            pass

class SetproctitleTestCase(unittest.TestCase):
    """Test the module works as expected.

    The tests are executed in external processes: setproctitle should
    never be imported directly from here.

    The tests scrits are written in Python 2 syntax: if the test suite is run
    with Python 3 they are converted automatically. This test module should
    be converted though: the Makefile should do that.
    """
    def test_runner(self):
        """Test the script execution method."""
        rv = self.run_script("""
            print 10 + 20
            """)
        self.assertEqual(rv, "30\n")

    def test_init_getproctitle(self):
        """getproctitle() returns a sensible value at initial call."""
        rv = self.run_script("""
            import setproctitle
            print setproctitle.getproctitle()
            """,
            args="-u")
        self.assertEqual(rv, sys.executable + " -u\n")

    def test_setproctitle(self):
        """setproctitle() can set the process title, duh."""
        rv = self.run_script(r"""
            import setproctitle
            setproctitle.setproctitle('Hello, world!')

            import os
            print os.getpid()
            # ps can fail on kfreebsd arch
            # (http://bugs.debian.org/cgi-bin/bugreport.cgi?bug=460331)
            print os.popen("ps -o pid,command 2> /dev/null").read()
            """)
        lines = filter(None, rv.splitlines())
        pid = lines.pop(0)
        pids = dict([r.strip().split(None, 1) for r in lines])

        title = self._clean_up_title(pids[pid])
        self.assertEqual(title, "Hello, world!")

    def test_prctl(self):
        """Check that prctl is called on supported platforms."""
        linux_version = []
        if sys.platform == 'linux2':
            try:
                linux_version = map(int,
                    re.search("[.0-9]+", os.popen("uname -r").read())
                        .group().split(".")[:3])
            except:
                pass

        if linux_version < [2,6,9]:
            raise SkipTest("syscall not supported")

        rv = self.run_script(r"""
            import setproctitle
            setproctitle.setproctitle('Hello, prctl!')
            print open('/proc/self/status').read()
            """)
        status = dict([r.split(':', 1) for r in rv.splitlines() if ':' in r])
        self.assertEqual(status['Name'].strip(), "Hello, prctl!")

    def test_getproctitle(self):
        """getproctitle() can read the process title back."""
        rv = self.run_script(r"""
            import setproctitle
            setproctitle.setproctitle('Hello, world!')
            print setproctitle.getproctitle()
            """)
        self.assertEqual(rv, "Hello, world!\n")

    def test_environ(self):
        """Check that clobbering environ didn't break env."""
        rv = self.run_script(r"""
            import setproctitle
            setproctitle.setproctitle('Hello, world! ' + 'X' * 1024)

            # set a new env variable, update another one
            import os
            os.environ['TEST_SETENV'] = "setenv-value"
            os.environ['PATH'] = os.environ.get('PATH', '') \
                    + os.pathsep + "fakepath"

            # read the environment from a spawned process inheriting the
            # updated env
            newenv = dict([r.split("=",1)
                    for r in os.popen("env").read().splitlines()
                    if '=' in r])

            print setproctitle.getproctitle()
            print newenv['TEST_SETENV']
            print newenv['PATH']
            """)

        title, test, path = rv.splitlines()
        self.assert_(title.startswith("Hello, world! XXXXX"), title)
        self.assertEqual(test, 'setenv-value')
        self.assert_(path.endswith('fakepath'), path)

    def test_issue_8(self):
        """Test that the module works with 'python -m'."""
        module = 'spt_issue_8'
        pypath = os.environ.get('PYTHONPATH', None)
        dir = tempfile.mkdtemp()
        os.environ['PYTHONPATH'] = dir + os.pathsep + (pypath or '')
        try:
            open(dir + '/' + module + '.py', 'w').write(
                self.to3(self._clean_whitespaces(r"""
                    import setproctitle
                    setproctitle.setproctitle("Hello, module!")

                    import os
                    print os.getpid()
                    print os.popen("ps -o pid,command 2> /dev/null").read()
                """)))

            rv = self.run_script(args="-m " + module)
            lines = filter(None, rv.splitlines())
            pid = lines.pop(0)
            pids = dict([r.strip().split(None, 1) for r in lines])

            title = self._clean_up_title(pids[pid])
            self.assertEqual(title, "Hello, module!")

        finally:
            shutil.rmtree(dir, ignore_errors=True)
            if pypath is not None:
                os.environ['PYTHONPATH'] = pypath
            else:
                del os.environ['PYTHONPATH']

    def test_unicode(self):
        """Title can contain unicode characters."""
        if 'utf-8' != sys.getdefaultencoding():
            raise SkipTest("encoding '%s' can't deal with snowmen"
                    % sys.getdefaultencoding())

        rv = self.run_script(r"""
            snowman = u'\u2603'

            import setproctitle
            setproctitle.setproctitle("Hello, " + snowman + "!")

            import os
            print os.getpid()
            print os.popen("ps -o pid,command 2> /dev/null").read()
        """)
        lines = filter(None, rv.splitlines())
        pid = lines.pop(0)
        pids = dict([r.strip().split(None, 1) for r in lines])

        snowmen = [
            u'\u2603',          # ps supports unicode
            r'\M-b\M^X\M^C',    # ps output on BSD
            r'M-bM^XM^C',       # ps output on OS-X
        ]
        title = self._clean_up_title(pids[pid])
        for snowman in snowmen:
            if title == "Hello, " + snowman + "!":
                break
        else:
            self.fail("unexpected ps output: %r" % title)

    def test_weird_args(self):
        """No problem with encoded arguments."""
        euro = u'\u20ac'
        snowman = u'\u2603'
        try:
            rv = self.run_script(r"""
            import setproctitle
            setproctitle.setproctitle("Hello, weird args!")

            import os
            print os.getpid()
            print os.popen("ps -o pid,command 2> /dev/null").read()
            """, args=u" ".join(["-", "hello", euro, snowman]))
        except TypeError:
            raise SkipTest(
                "apparently we can't pass unicode args to a program")

        lines = filter(None, rv.splitlines())
        pid = lines.pop(0)
        pids = dict([r.strip().split(None, 1) for r in lines])

        title = self._clean_up_title(pids[pid])
        self.assertEqual(title, "Hello, weird args!")

    def test_weird_path(self):
        """No problem with encoded argv[0] path."""
        self._check_4388()
        euro = u'\u20ac'
        snowman = u'\u2603'
        tdir = tempfile.mkdtemp()
        dir = tdir + "/" + euro + "/" + snowman
        try:
            try:
                os.makedirs(dir)
            except UnicodeEncodeError:
                raise SkipTest("file system doesn't support unicode")

            exc = dir + "/python"
            os.symlink(sys.executable, exc)

            rv = self.run_script(r"""
                import setproctitle
                setproctitle.setproctitle("Hello, weird path!")

                import os
                print os.getpid()
                print os.popen("ps -o pid,command 2> /dev/null").read()
                """,
                args=u" ".join(["-", "foo", "bar", "baz"]),
                executable=exc)
            lines = filter(None, rv.splitlines())
            pid = lines.pop(0)
            pids = dict([r.strip().split(None, 1) for r in lines])

            title = self._clean_up_title(pids[pid])
            self.assertEqual(title, "Hello, weird path!")
        finally:
            shutil.rmtree(tdir, ignore_errors=True)

    def run_script(self, script=None, args=None, executable=None):
        """run a script in a separate process.

        if the script completes successfully, return its ``stdout``,
        else fail the test.
        """
        if executable is None:
            executable = sys.executable

        cmdline = executable
        if args:
            cmdline = cmdline + " " + args

        proc = Popen(cmdline,
                stdin=PIPE, stdout=PIPE, stderr=PIPE,
                shell=True, close_fds=True)

        if script is not None:
            script = self._clean_whitespaces(script)
            script = self.to3(script)
            if IS_PY3K:
                script = script.encode()

        out, err = proc.communicate(script)
        if 0 != proc.returncode:
            print out
            print err
            self.fail("test script failed")

        # Py3 subprocess generates bytes strings.
        if IS_PY3K:
            out = out.decode()

        return out

    def to3(self, script):
        """Convert a script to Python3 if required."""
        if not IS_PY3K:
            return script

        script = script.encode()
        f = tempfile.NamedTemporaryFile(suffix=".py")
        f.write(script)
        f.flush()

        # 2to3 is way too chatty
        import logging
        logging.basicConfig(filename=os.devnull)

        from lib2to3.main import main
        if main("lib2to3.fixes", ['--no-diffs', '-w', '-n', f.name]):
            raise Exception('py3 conversion failed')

        return open(f.name).read()

    def _clean_whitespaces(self, script):
        """clean up a script in a string

        Remove the amount of whitelines found in the first nonblank line
        """
        script = script.splitlines(True)
        while script and script[0].isspace():
            script.pop(0)

        if not script:
            raise ValueError("empty script")

        line1 = script[0]
        spaces = script[0][:-len(script[0].lstrip())]
        assert spaces.isspace()

        for i, line in enumerate(script):
            if line.isspace(): continue
            if line.find(spaces) != 0:
                raise ValueError("inconsistent spaces at line %d (%s)"
                        % (i + 1, line.strip()))
            script[i] = line[len(spaces):]

        # drop final blank lines: they produce import errors
        while script and script[-1].isspace():
            del script[-1]

        assert not script[0][0].isspace(), script[0]
        return ''.join(script)

    def _clean_up_title(self, title):
        """Clean up a string from the prefix added by the platform.
        """
        # BSD's setproctitle decorates the title with the process name.
        if 'bsd' in sys.platform:
            procname = os.path.basename(sys.executable)
            title = ' '.join([t for t in title.split(' ')
                if procname not in t])  

        return title

    def _check_4388(self):
        """Check if the system is affected by bug #4388.

        If positive, unicode chars in the cmdline are not reliable,
        so bail out.

        see: http://bugs.python.org/issue4388
        """
        if not IS_PY3K:
            return

        if sys.getfilesystemencoding() == 'ascii':
            # in this case the char below would get translated in some
            # inconsistent way.
            # I'm not getting why the FS encoding is involved in process
            # spawning, the whole story just seems a gigantic can of worms.
            return

        from subprocess import Popen, PIPE
        p = Popen([sys.executable, '-c', "ord('\xe9')"], stderr=PIPE)
        p.communicate()
        if p.returncode:
            raise SkipTest("bug #4388 detected")


if __name__ == '__main__':
    unittest.main()
