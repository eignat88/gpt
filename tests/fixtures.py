XPO_SAMPLE = """
Exportfile for AOT version 1.0 or later
Formatversion: 1

***Element: CLS

; Microsoft Dynamics AX Class: Demo unloaded
; --------------------------------------------------------------------------------
  CLSVERSION 1

SOURCE #run
public void run()
{
    if (SalesIdRange)
    {
        while (name)
        {
            switch (SalesIdRange)
            {
                case 1:
                    this.helper(SalesIdRange);
                    break;
            }
        }
    }

    select firstOnly custTable;
    other.doWork();
}
ENDSOURCE
SOURCE #helper
private void helper(SalesIdRange _salesIdRange)
{
    ttsBegin;
    while select forUpdate salesTable
    {
        salesTable.update();
    }
    tableBuffer.insert();
    tableBuffer.delete();
}
ENDSOURCE
"""
