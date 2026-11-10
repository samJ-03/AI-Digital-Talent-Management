"""Export the exact published-prompt schema without database or provider calls."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.evaluation.match_scoring import MatchDraft

if __name__=='__main__':
    print(json.dumps(MatchDraft.model_json_schema(),ensure_ascii=False,indent=2))
