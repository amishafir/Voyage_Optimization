$ErrorActionPreference = "Continue"

$destination = "C:\Users\amish\Projects\Thesis\paper_workspace\data\.incoming_shlomo2_20260816"
New-Item -ItemType Directory -Path $destination -Force | Out-Null

Write-Host "Downloading the two Shlomo2 HDF5 files to:" -ForegroundColor Cyan
Write-Host $destination
Write-Host "Enter your TAU password when prompted (possibly once per file)." -ForegroundColor Yellow

& scp.exe -p `
    "amishafir@Shlomo2-pcl.eng.tau.ac.il:~/Ami/pipeline/data/experiment_b_138wp.h5" `
    "amishafir@Shlomo2-pcl.eng.tau.ac.il:~/Ami/pipeline/data/experiment_d_391wp.h5" `
    "$destination\"

if ($LASTEXITCODE -eq 0) {
    Write-Host "DOWNLOAD_COMPLETE" -ForegroundColor Green
} else {
    Write-Host "DOWNLOAD_FAILED exit=$LASTEXITCODE" -ForegroundColor Red
}

Read-Host "Press Enter to close"
