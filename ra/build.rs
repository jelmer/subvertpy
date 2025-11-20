use std::process::Command;

fn main() {
    // Try to get SVN_VER_REVISION from pkg-config include path and the header
    let svn_revision = get_svn_ver_revision().unwrap_or(0);
    println!("cargo:rustc-env=SVN_VER_REVISION={}", svn_revision);
}

fn get_svn_ver_revision() -> Option<i64> {
    // Try pkg-config first to find include dir
    let output = Command::new("pkg-config")
        .args(["--cflags-only-I", "libsvn_subr"])
        .output()
        .ok()?;
    let cflags = String::from_utf8(output.stdout).ok()?;

    for flag in cflags.split_whitespace() {
        if let Some(dir) = flag.strip_prefix("-I") {
            let header = std::path::Path::new(dir).join("svn_version.h");
            if header.exists() {
                let content = std::fs::read_to_string(&header).ok()?;
                for line in content.lines() {
                    if line.contains("SVN_VER_REVISION") && !line.contains("/*") {
                        // Parse: #define SVN_VER_REVISION   1922182
                        let parts: Vec<&str> = line.split_whitespace().collect();
                        if parts.len() >= 3 && parts[1] == "SVN_VER_REVISION" {
                            return parts[2].parse().ok();
                        }
                    }
                }
            }
        }
    }
    None
}
