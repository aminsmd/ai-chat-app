@socketio.on('update_personality')
def handle_personality_update(data):
    """Handle personality update from client"""
    try:
        room_id = session.get('room_id')
        if not room_id or room_id not in rooms:
            return
        
        # Get the current personality
        current_personality = rooms[room_id].get('personality', default_personality)
        
        # Convert UI data to personality object
        from core.personality import Personality
        updated_personality = Personality.from_ui_data(data, current_personality)
        
        # Save updated personality
        rooms[room_id]['personality'] = updated_personality
        
        # Save to database if available
        if hasattr(app, 'db_manager'):
            app.db_manager.save_persona(room_id, updated_personality)
        
        # Broadcast update to all clients in the room
        emit('personality_updated', updated_personality.to_dict(), room=room_id)
        
        logger.info(f"Personality updated for room {room_id}")
        
    except Exception as e:
        logger.error(f"Error updating personality: {str(e)}", exc_info=True)

@app.route('/chat/<room_id>')
def chat(room_id):
    """Chat room page"""
    if room_id not in rooms:
        flash('Room not found')
        return redirect(url_for('index'))
    
    # Get session username or redirect to join
    username = session.get('username')
    if not username:
        return redirect(url_for('join', room_id=room_id))
    
    # Get current participants
    participants = list(rooms[room_id].get('participants', {}).values())
    
    # Get room name
    room_name = rooms[room_id].get('name', f"Room {room_id}")
    
    # Get personality
    personality = rooms[room_id].get('personality', default_personality)
    
    # Get behavior map for the personality using personality_to_behavior
    from core.personality import personality_to_behavior
    behavior_map = personality_to_behavior(personality.traits)
    
    # Get task if exists
    task = None
    if hasattr(app, 'db_manager'):
        task = app.db_manager.load_task(room_id)
    
    # Generate share URL
    share_url = url_for('join', room_id=room_id, _external=True)
    
    return render_template('chat.html', 
                          room_id=room_id, 
                          room_name=room_name, 
                          username=username, 
                          participants=participants,
                          share_url=share_url,
                          personality=personality,
                          behavior_map=behavior_map,
                          task=task)

@app.route('/create_room', methods=['POST'])
def create_room():
    """Create a new chat room"""
    room_name = request.form.get('room_name')
    username = request.form.get('name')
    
    if not room_name or not username:
        flash('Room name and your name are required.')
        return redirect(url_for('index'))
    
    # Generate a unique room ID
    room_id = str(uuid.uuid4())
    
    # Create a copy of the default personality
    from core.personality import Personality, default_personality
    room_personality = Personality(
        name=default_personality.name,
        description=default_personality.description,
        traits=default_personality.traits.copy(),
        communication_style={},  # Empty dict as we're not using communication style
        response_characteristics=default_personality.response_characteristics.copy()
    )
    
    # Create room with default personality
    rooms[room_id] = {
        'name': room_name,
        'participants': [username],
        'personality': room_personality,
        'messages': []
    }
    
    # Save personality to database if available
    if hasattr(app, 'db_manager'):
        app.db_manager.save_persona(room_id, room_personality)
    
    # Store username in session
    session['username'] = username
    session['room_id'] = room_id
    
    # Join the room
    return redirect(url_for('chat', room_id=room_id)) 