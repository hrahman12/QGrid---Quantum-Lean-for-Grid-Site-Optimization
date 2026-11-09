from api.quantum import handler as QuantumHandler
from viz.webgl.server.physics_service import execute_physics


class handler(QuantumHandler):
    def execute_job(self, settings):
        return execute_physics(settings)
