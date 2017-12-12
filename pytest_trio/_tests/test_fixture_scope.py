import pytest


@pytest.mark.xfail(reason='Scope check not implemented yet')
@pytest.mark.parametrize('scope', ['class', 'module', 'session'])
def test_not_allowed_scopes(testdir, scope):

    testdir.makepyfile("""
        import pytest

        @pytest.fixture(scope=%r)
        async def fix1():
            return 'fix1'

        @pytest.mark.trio
        async def test_base(fix1):
            pass  # Crash should have occures before arriving here
    """ % scope)

    result = testdir.runpytest()

    result.assert_outcomes(error=1)


@pytest.mark.parametrize('scope', ['function'])
def test_allowed_scopes(testdir, scope):

    testdir.makepyfile("""
        import pytest

        @pytest.fixture(scope=%r)
        async def fix1():
            return 'fix1'

        @pytest.mark.trio
        async def test_base(fix1):
            assert fix1 == 'fix1'
    """ % scope)

    result = testdir.runpytest()

    result.assert_outcomes(passed=1)
