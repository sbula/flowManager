from flow.engine.atoms import Atom, AtomResult


class MockGitAtom(Atom):
    def run(self, context, **kwargs):
        return AtomResult(True, "Git Ran")
