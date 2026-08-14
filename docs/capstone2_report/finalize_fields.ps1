# Open the built report in Word, refresh every field (table of contents, list of
# tables, list of figures, page numbers), repaginate, report the page count and save.
param([string]$Path = "$PSScriptRoot\Capstone_II_Report.docx")

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$doc = $word.Documents.Open($Path, $false, $false)

foreach ($story in $doc.StoryRanges) { $null = $story.Fields.Update() }
foreach ($toc in $doc.TablesOfContents) { $toc.Update() }
foreach ($tof in $doc.TablesOfFigures) { $tof.Update() }
foreach ($story in $doc.StoryRanges) { $null = $story.Fields.Update() }

$doc.Repaginate()
$pages = $doc.ComputeStatistics(2)   # wdStatisticPages
$words = $doc.ComputeStatistics(0)   # wdStatisticWords
Write-Output "PAGES=$pages WORDS=$words"

$doc.Save()
$doc.Close(0)
$word.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
