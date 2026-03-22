#include <windows.h>
#include <wincred.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#pragma comment(lib, "Advapi32.lib")

#define CRED_TYPE_GENERIC 1

void print_error(const char* prefix) {
    DWORD err = GetLastError();
    wchar_t* msg = NULL;

    FormatMessageW(
        FORMAT_MESSAGE_ALLOCATE_BUFFER | FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS,
        NULL,
        err,
        MAKELANGID(LANG_ENGLISH, SUBLANG_DEFAULT),  // 强制英文
        (LPWSTR)&msg,
        0,
        NULL
    );

    if (msg) {
        printf("%s: (%lu) ", prefix, err);
        wprintf(L"%ls\n", msg);
        LocalFree(msg);
    } else {
        printf("%s: Unknown error (%lu)\n", prefix, err);
    }
}

static int is_probably_utf16le_text(const BYTE* data, DWORD size) {
    if (!data || size < 2 || (size % 2) != 0) {
        return 0;
    }

    DWORD zero_count = 0;
    DWORD pairs = size / 2;
    for (DWORD i = 1; i < size; i += 2) {
        if (data[i] == 0) {
            zero_count++;
        }
    }

    return zero_count > 0 && zero_count >= (pairs * 8) / 10;
}

static void print_credential_blob(const BYTE* blob, DWORD size) {
    if (!blob || size == 0) {
        printf("\n");
        return;
    }

    if (is_probably_utf16le_text(blob, size)) {
        int wlen = (int)(size / sizeof(wchar_t));
        int out_len = WideCharToMultiByte(CP_UTF8, 0, (const wchar_t*)blob, wlen, NULL, 0, NULL, NULL);
        if (out_len > 0) {
            char* out = (char*)malloc((size_t)out_len + 1);
            if (out) {
                WideCharToMultiByte(CP_UTF8, 0, (const wchar_t*)blob, wlen, out, out_len, NULL, NULL);
                out[out_len] = '\0';
                printf("%s\n", out);
                free(out);
                return;
            }
        }
    }

    fwrite(blob, 1, size, stdout);
    fputc('\n', stdout);
}

void save(const char* target, const char* username, const char* password) {
    CREDENTIALA cred = {0};

    // 拼接 usrname = target:username
    char usrname[256];
    snprintf(usrname, sizeof(usrname), "%s@%s", username, target);

    cred.Type = CRED_TYPE_GENERIC;
    cred.TargetName = (LPSTR)usrname;
    cred.UserName = (LPSTR)username;

    cred.CredentialBlobSize = (DWORD)strlen(password);
    cred.CredentialBlob = (LPBYTE)password;

    cred.Persist = CRED_PERSIST_LOCAL_MACHINE;

    if (CredWriteA(&cred, 0)) {
        printf("OK\n");
    } else {
        print_error("Save Password failed");
    }
}

void read(const char* service, const char* username) {
    char target_new[256];

    // username@service
    snprintf(target_new, sizeof(target_new), "%s@%s", username, service);

    wchar_t wtarget[256];
    MultiByteToWideChar(CP_UTF8, 0, target_new, -1, wtarget, 256);

    PCREDENTIALW pcred;

    if (CredReadW(wtarget, CRED_TYPE_GENERIC, 0, &pcred)) {
        print_credential_blob(pcred->CredentialBlob, pcred->CredentialBlobSize);
        CredFree(pcred);
        return;
    }

    DWORD err = GetLastError();

    // fallback 旧格式
    if (err == ERROR_NOT_FOUND) {

        MultiByteToWideChar(CP_UTF8, 0, service, -1, wtarget, 256);

        if (CredReadW(wtarget, CRED_TYPE_GENERIC, 0, &pcred)) {

            if (pcred->UserName) {
                char uname[256];
                WideCharToMultiByte(CP_UTF8, 0, pcred->UserName, -1, uname, 256, NULL, NULL);

                if (strcmp(uname, username) == 0)
                    print_credential_blob(pcred->CredentialBlob, pcred->CredentialBlobSize);
                else
                    printf("NULL\n");
            } else {
                printf("NULL\n");
            }

            CredFree(pcred);
            return;
        }

        if (GetLastError() == ERROR_NOT_FOUND) {
            printf("NULL\n");
            return;
        }
    }

    // 其他错误
    print_error("Read Password failed");
}

void del(const char* service, const char* username) {
    char target_new[256];

    // 新格式：user@InterKnot
    snprintf(target_new, sizeof(target_new), "%s@%s", username, service);

    // 删新格式
    if (CredDeleteA(target_new, CRED_TYPE_GENERIC, 0)) {
        printf("OK\n");
        return;
    }

    DWORD err = GetLastError();
    // 如果没找到，检查旧格式
    if (err == ERROR_NOT_FOUND) {
        PCREDENTIALA pcred;

        // 读取旧格式
        if (CredReadA(service, CRED_TYPE_GENERIC, 0, &pcred)) {

            // 判断是不是同一个用户
            if (pcred->UserName && strcmp(pcred->UserName, username) == 0) {

                CredFree(pcred);
                // 删除旧格式
                if (CredDeleteA(service, CRED_TYPE_GENERIC, 0)) {
                    printf("OK\n");
                    return;
                } else {
                    print_error("Delete Password failed");
                    return;
                }
            }
            // 用户不匹配，不删除
            CredFree(pcred);
            printf("NOT_FOUND\n");
            return;
        }
        err = GetLastError();
        if (err == ERROR_NOT_FOUND) {
            printf("NOT_FOUND\n");
            return;
        }
    }

    print_error("Delete Password failed");
}

void list(const char* filter) {
    DWORD count = 0;
    PCREDENTIALA *creds = NULL;

    if (!CredEnumerateA(NULL, 0, &count, &creds)) {
        print_error("List Passwords failed");
        return;
    }

    for (DWORD i = 0; i < count; i++) {
        PCREDENTIALA cred = creds[i];

        if (cred->UserName) {
            // filter 匹配 target
            if (!filter || (cred->TargetName && strstr(cred->TargetName, filter))) {
                printf("%s\n", cred->UserName);
            }
        }
    }

    CredFree(creds);
}

int main(int argc, char* argv[]) {

    if (argc < 2) {
        printf("Usage:\n");
        printf("  save target username password\n");
        printf("  read target\n");
        printf("  delete target\n");
        printf("  list [filter]\n");
        return 1;
    }

    if (strcmp(argv[1], "save") == 0 && argc == 5) {
        save(argv[2], argv[3], argv[4]);
    }
    else if (strcmp(argv[1], "read") == 0 && argc == 3) {
        read("InterKnot", argv[2]);
    }
    else if (strcmp(argv[1], "delete") == 0 && argc == 3) {
        del("InterKnot", argv[2]);
    }
    else if (strcmp(argv[1], "list") == 0) {
        if (argc == 3)
            list(argv[2]);   // 带过滤
        else
            list(NULL);      // 全部
    }
    else {
        printf("Invalid command\n");
    }

    return 0;
}