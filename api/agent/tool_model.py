class ToolResponse:
    def __init__(self, response, metadata : dict= None):
        self.response = response
        self.metadata = metadata or {}