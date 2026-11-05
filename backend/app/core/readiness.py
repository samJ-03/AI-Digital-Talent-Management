from sqlalchemy import create_engine, select, literal
from redis import Redis
from app.core.settings import Settings

class InfrastructureProbe:
    def __init__(self, settings: Settings):
        self.engine = create_engine(settings.database_url.get_secret_value(), pool_pre_ping=True, connect_args={'connect_timeout':2})
        self.redis = Redis.from_url(settings.redis_url.get_secret_value(), socket_timeout=2, socket_connect_timeout=2)

    def check(self) -> dict[str, bool]:
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
        self.engine.dispose()
        self.redis.close()
