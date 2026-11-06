"""生成项目独立的本地配置；只创建新文件，不覆盖现有秘密。"""
import argparse
import base64
import os
from pathlib import Path
import secrets

def create_environment(destination: Path, template: Path) -> None:
    """将随机凭据写入新文件；连接URL与所生成的密码保持一致。"""
    mysql=secrets.token_urlsafe(32)
    redis=secrets.token_urlsafe(32)
    values={
        'TALENT_MYSQL_ROOT_PASSWORD':secrets.token_urlsafe(32),
        'TALENT_MYSQL_PASSWORD':mysql,
        'TALENT_REDIS_PASSWORD':redis,
        'TALENT_MINIO_USER':'talent-'+secrets.token_hex(6),
        'TALENT_MINIO_PASSWORD':secrets.token_urlsafe(32),
        'TALENT_MONITOR_TOKEN':secrets.token_urlsafe(48),
        'TALENT_DATABASE_URL':f'mysql+pymysql://talent:{mysql}@mysql:3306/talent_dev?charset=utf8mb4',
        'TALENT_TEST_DATABASE_URL':f'mysql+pymysql://talent:{mysql}@mysql-test:3306/talent_test?charset=utf8mb4',
        'TALENT_REDIS_URL':f'redis://:{redis}@redis:6379/0',
        'TALENT_ENCRYPTION_KEY':base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('ascii'),
    }
    lines=[]
    for line in template.read_text(encoding='utf8').splitlines():
        key=line.split('=',1)[0]
        lines.append(key+'='+values[key] if key in values else line)
    # O_EXCL protects existing .env even if another process creates it concurrently.
    fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w',encoding='utf8',newline='\n') as stream:
        stream.write('\n'.join(lines)+'\n')

def main() -> int:
    """创建本地.env，不显示任何密码、API Key或加密主密钥。"""
    root=Path(__file__).resolve().parents[1]
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=root/'.env',help='新建配置文件的位置；已有文件将拒绝覆盖')
    args=parser.parse_args()
    try: create_environment(args.output,root/'.env_example')
    except FileExistsError:
        print('配置文件已存在，未修改任何内容。')
        return 1
    print('本地配置已创建；秘密未显示。请保留此文件和加密主密钥，不要提交Git。')
    return 0

if __name__=='__main__': raise SystemExit(main())
