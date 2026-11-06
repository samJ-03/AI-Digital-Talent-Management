"""公共基础设施：检查核心依赖的实际就绪状态。"""
from sqlalchemy import create_engine, select, literal
from redis import Redis
from app.core.settings import Settings

class InfrastructureProbe:
    """InfrastructureProbe：公共基础设施中的协作类型。"""
    def __init__(self, settings: Settings):
        self.engine = create_engine(settings.database_url.get_secret_value(), pool_pre_ping=True, connect_args={'connect_timeout':2})
        self.redis = Redis.from_url(settings.redis_url.get_secret_value(), socket_timeout=2, socket_connect_timeout=2)

    def check(self) -> dict[str, bool]:
        """检查实际依赖或配置状态，并返回明确结果。"""
        state = {'mysql':False, 'redis':False}
        try:
            with self.engine.connect() as connection:
                state['mysql'] = connection.execute(select(literal(1))).scalar_one() == 1
        except Exception:
            pass
        try:
            state['redis'] = self.redis.ping() is True
        except Exception:
            pass
        return state

    def close(self) -> None:
        """释放本对象持有的外部连接。"""
        self.engine.dispose()
        self.redis.close()
