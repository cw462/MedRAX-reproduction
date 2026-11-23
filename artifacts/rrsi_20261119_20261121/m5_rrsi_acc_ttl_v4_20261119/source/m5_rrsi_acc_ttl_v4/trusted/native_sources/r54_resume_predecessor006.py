"""Add the actual R56 parser005 protocol to R54's unchanged full-completion gate."""
PROTOCOL = ('protocol_governance_recovery006.json', 'r56_single_received_merge_delimiter_recovery_v1')


def install():
    import r54_resume_schedule as schedule
    matching = [value for value in schedule.PROTOCOLS if value[0] == PROTOCOL[0]]
    if matching and matching != [PROTOCOL]:
        raise ValueError('R54_predecessor006_schema_conflict')
    if not matching:
        schedule.PROTOCOLS = (*schedule.PROTOCOLS, PROTOCOL)
    return schedule.PROTOCOLS
