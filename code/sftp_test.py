import sys, os
sys.path.insert(0, "medrax_work")
import remote
c = remote.connect()
sftp = c.open_sftp()
print("cwd:", sftp.getcwd())
for dest in ["/home/imss/cw/radiology_rag_p3/test.md"]:
    try:
        sftp.put("rag_eval/REPORT.md", dest)
        print("OK abs", dest, sftp.stat(dest).st_size)
    except Exception as e:
        print("FAIL abs", dest, repr(e)[:200])
try:
    sftp.chdir("/home/imss/cw/radiology_rag_p3")
    sftp.put("rag_eval/REPORT.md", "test2.md")
    print("OK rel", sftp.stat("test2.md").st_size)
except Exception as e:
    print("FAIL rel", repr(e)[:200])
sftp.close(); c.close()
