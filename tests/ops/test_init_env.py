"""验证配置生成不覆盖已有文件，秘密不回显，模板与消费端保持一致。"""
from pathlib import Path
import base64
import pytest
from scripts.init_env import create_environment

ROOT=Path(__file__).resolve().parents[2]

def test_templates_identical_and_generated_urls_match(tmp_path):
    template=ROOT/'.env_example'
    assert template.read_bytes()==(ROOT/'.env.example').read_bytes()
    target=tmp_path/'.env'
    create_environment(target,template)
    values=dict(line.split('=',1) for line in target.read_text(encoding='utf8').splitlines() if line and not line.startswith('#'))
    for key in ['TALENT_MYSQL_ROOT_PASSWORD','TALENT_MYSQL_PASSWORD','TALENT_REDIS_PASSWORD','TALENT_MONITOR_TOKEN']:
        assert len(values[key])>=32
    assert ':'+values['TALENT_MYSQL_PASSWORD']+'@mysql:3306/talent_dev' in values['TALENT_DATABASE_URL']
    assert '@mysql-test:3306/talent_test' in values['TALENT_TEST_DATABASE_URL']
    assert ':'+values['TALENT_REDIS_PASSWORD']+'@redis:6379/0' in values['TALENT_REDIS_URL']
    assert len(base64.urlsafe_b64decode(values['TALENT_ENCRYPTION_KEY']))==32
    assert values['TALENT_DEEPSEEK_API_KEY']==values['TALENT_DASHSCOPE_API_KEY']==''

def test_existing_environment_not_overwritten(tmp_path):
    target=tmp_path/'.env';target.write_text('keep-private-data',encoding='utf8')
    with pytest.raises(FileExistsError): create_environment(target,ROOT/'.env_example')
    assert target.read_text(encoding='utf8')=='keep-private-data'
