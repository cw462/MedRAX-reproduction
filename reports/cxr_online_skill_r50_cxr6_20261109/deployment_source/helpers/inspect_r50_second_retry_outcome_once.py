"""Use the same read-only capture routine for ONLY the new second attempt."""
import inspect_r50_retry_outcome as capture
from deploy_cxr6_r50 import RUN,PREP

if __name__=='__main__':
    capture.REMOTE=RUN+'/technical_recovery/002_medgemma_tokenizer_load'
    capture.LOCAL=PREP/'failures/002_chex_183/explicit_retry'
    capture.main()
