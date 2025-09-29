
import api.agent.usualagent
def format_time_h_m_s(seconds):
    s = seconds
    m = 0
    h = 0
    q = int(s/60)
    s = s - (q*60)
    m = m + q
    q = int(m / 60)
    m = m - (q * 60)
    h = h + q
    sformat = str(s)
    mformat = str(m)
    hformat = str(h)
    if s < 10 :
        sformat = "0" + sformat
    if m < 10 :
        mformat = "0" + mformat
    if h < 10 :
        hformat = "0" + hformat
    return f"{hformat}:{mformat}:{sformat}"
