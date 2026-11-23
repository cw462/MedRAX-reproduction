"""Same R54 answer service; cross-case Skill requests remain disabled."""
from pathlib import Path
from skill_services_r54 import Services as Original


class Services(Original):
    def set_candidates(self, skills):
        if skills:
            raise ValueError('R54_resume_only_Skill_off_authorized')
        return super().set_candidates(skills)

    def meta(self, *args, **kwargs):
        raise RuntimeError('R54_resume_Skill_off_META_forbidden')

    def embed(self, *args, **kwargs):
        raise RuntimeError('R54_resume_Skill_off_embedding_forbidden')

    def execute(self, row, policy, data, conditioning):
        if self.tools is None:
            from tools_r54_off_resume002 import Tools
            self.tools = Tools(self.runtime, Path(data), self.out)
        return super().execute(row, policy, data, conditioning)
