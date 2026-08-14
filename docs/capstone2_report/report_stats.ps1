# Report the page on which each Heading 1 starts, so the chapter span can be checked
# against the guideline's page budget.
param([string]$Path = "$PSScriptRoot\Capstone_II_Report.docx")

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$doc = $word.Documents.Open($Path, $false, $true)
$doc.Repaginate()

foreach ($p in $doc.Paragraphs) {
    if ($p.OutlineLevel -eq 1) {
        $t = $p.Range.Text.Trim()
        if ($t.Length -gt 0) {
            $pg = $p.Range.Information(3)   # wdActiveEndPageNumber
            Write-Output ("{0,4}  {1}" -f $pg, $t)
        }
    }
}
Write-Output ("TOTAL PAGES = {0}" -f $doc.ComputeStatistics(2))
$doc.Close(0)
$word.Quit()
