class RoomNotFoundError(Exception):
    def __init__(self, room_id: str):
        self.room_id = room_id
        super().__init__(f"Room {room_id} not found")

class DatabaseError(Exception):
    pass

class PipelineError(Exception):
    pass 