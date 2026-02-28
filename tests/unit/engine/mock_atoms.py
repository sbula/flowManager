from flow.atoms import Atom, AtomResult, AtomStatus


class MockGitAtom(Atom):
    def run(self, context, **kwargs):
        return AtomResult(AtomStatus.SUCCESS, "Git Ran")
