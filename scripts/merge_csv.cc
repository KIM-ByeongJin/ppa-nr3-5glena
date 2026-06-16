#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <sstream>
#include <map>
#include <cstdio>
#include <algorithm> // sort 함수 사용을 위해 추가

using namespace std;

// 정렬을 위해 각 행의 데이터와 기준이 되는 Time 값을 저장할 구조체
struct LogRow {
    double timeValue;
    string csvLine;
};

// 1. 탭(\t)만을 구분자로 사용하여 문자열을 분리하는 함수 (파일 전처리 용도)
vector<string> splitByTab(const string& str) {
    vector<string> tokens;
    stringstream ss(str);
    string token;
    while (getline(ss, token, '\t')) {
        if (!token.empty() && token.back() == '\r') token.pop_back(); 
        tokens.push_back(token);
    }
    if (!str.empty() && str.back() == '\t') tokens.push_back("");
    return tokens;
}

// 2. 첫 행(헤더)에서만 VarTTI를 지우고, 나머지 열은 그대로 복사하는 전처리 함수
bool preprocessFileToRemoveVarTTI(const string& fileName) {
    ifstream inFile(fileName);
    if (!inFile.is_open()) return false;

    string headerLine;
    if (!getline(inFile, headerLine)) return false;

    if (headerLine.find("VarTTI") == string::npos) {
        inFile.close();
        return false; 
    }

    string tmpFileName = fileName + ".tmp";
    ofstream outFile(tmpFileName);
    
    vector<string> headers = splitByTab(headerLine);
    bool first = true;
    for (int i = 0; i < (int)headers.size(); ++i) {
        if (headers[i].find("VarTTI") != string::npos) continue; 
        if (!first) outFile << "\t";
        outFile << headers[i];
        first = false;
    }
    outFile << "\n";

    string line;
    while (getline(inFile, line)) {
        outFile << line << "\n";
    }

    inFile.close();
    outFile.close();

    remove(fileName.c_str());
    rename(tmpFileName.c_str(), fileName.c_str());
    
    return true;
}

// 3. 빈 공간과 탭을 모두 구분자로 처리하여 문자열을 분리하는 함수
vector<string> splitBySpaceOrTab(const string& str) {
    vector<string> tokens;
    string token;
    for (char c : str) {
        if (c == ' ' || c == '\t' || c == '\r') { 
            if (!token.empty()) {
                tokens.push_back(token);
                token.clear();
            }
        } else {
            token += c;
        }
    }
    if (!token.empty()) {
        tokens.push_back(token);
    }
    return tokens;
}

// 4. 분리된 토큰 배열에서 Entity 패턴들을 찾아 하나로 묶어주는 함수
vector<string> mergeEntityTokens(vector<string> tokens) {
    for (int i = 0; i < (int)tokens.size(); i++) {
        if (tokens[i] == "UE" || tokens[i] == "gNB") {
            if (i + 1 < tokens.size() && (tokens[i+1] == "MAC" || tokens[i+1] == "Phy" || tokens[i+1] == "PHY")) {
                tokens[i] += " " + tokens[i+1];
                tokens.erase(tokens.begin() + i + 1);
                if (i + 1 < tokens.size() && (tokens[i+1] == "Txed" || tokens[i+1] == "Rxed")) {
                    tokens[i] += " " + tokens[i+1];
                    tokens.erase(tokens.begin() + i + 1);
                }
            }
        }
        else if (tokens[i] == "HARQ") {
            if (i + 1 < tokens.size() && tokens[i+1] == "FD") {
                tokens[i] += " " + tokens[i+1];
                tokens.erase(tokens.begin() + i + 1);
                if (i + 1 < tokens.size() && (tokens[i+1] == "Txed" || tokens[i+1] == "Rxed")) {
                    tokens[i] += " " + tokens[i+1];
                    tokens.erase(tokens.begin() + i + 1);
                }
            }
        }
        else if (tokens[i] == "DL" || tokens[i] == "UL") {
            if (i + 1 < tokens.size() && tokens[i+1] == "DCI") {
                tokens[i] += " " + tokens[i+1];
                tokens.erase(tokens.begin() + i + 1);
                if (i + 1 < tokens.size() && (tokens[i+1] == "Txed" || tokens[i+1] == "Rxed")) {
                    tokens[i] += " " + tokens[i+1];
                    tokens.erase(tokens.begin() + i + 1);
                }
            }
        }
    }
    return tokens;
}

int main() {
    vector<string> fileNames = {
        "NrDlPdcpRxStats.txt", "NrDlPdcpTxStats.txt",
        "NrDlRxRlcStats.txt", "NrDlTxRlcStats.txt", 
        "RxedGnbMacCtrlMsgsTrace.txt", "RxedGnbPhyCtrlMsgsTrace.txt", 
        "RxedUeMacCtrlMsgsTrace.txt", "RxedUePhyCtrlMsgsTrace.txt", 
        "RxedUePhyDlDciTrace.txt", 
        "TxedGnbMacCtrlMsgsTrace.txt", "TxedGnbPhyCtrlMsgsTrace.txt", 
        "TxedUeMacCtrlMsgsTrace.txt", "TxedUePhyCtrlMsgsTrace.txt"
    };

    vector<string> targetHeaders = {
        "Time", "Entity", "Frame", "SF", "Slot", "nodeId", "RNTI", "bwpId", "MsgType", "delay(s)", "packetSize"
    };

    // 파일 전체의 데이터를 모아둘 벡터
    vector<LogRow> allRecords;

    int successCount = 0;
    int skipCount = 0;

    cout << "========== 병합 작업 시작 ==========" << endl;

    for (const auto& fileName : fileNames) {
        if (preprocessFileToRemoveVarTTI(fileName)) {
            cout << "[전처리 완료] " << fileName << " (헤더에서만 VarTTI 삭제됨)" << endl;
        }

        ifstream inFile(fileName);
        if (!inFile.is_open()) {
            cout << "[건너뜀] 파일을 찾을 수 없습니다: " << fileName << endl;
            skipCount++;
            continue;
        }

        string line;
        bool isFirstLine = true;
        int rowCount = 0;
        
        map<string, int> headerIndexMap;

        while (getline(inFile, line)) {
            if (line.empty()) continue;

            if (isFirstLine) {
                vector<string> inputHeaders = splitBySpaceOrTab(line);
                for (int i = 0; i < (int)inputHeaders.size(); ++i) {
                    string headerName = inputHeaders[i];
                    if (headerName == "time(s)") headerName = "Time";
                    else if (headerName == "cellId") headerName = "nodeId";
                    else if (headerName == "rnti") headerName = "RNTI";
                    
                    headerIndexMap[headerName] = i;
                }
                isFirstLine = false;
                continue; 
            }

            vector<string> rawTokens = splitBySpaceOrTab(line);
            vector<string> columns = mergeEntityTokens(rawTokens);

            string csvLine = "";
            double timeVal = 0.0;

            for (size_t i = 0; i < targetHeaders.size(); ++i) {
                string colName = targetHeaders[i];
                string value = "";

                if (headerIndexMap.find(colName) != headerIndexMap.end()) {
                    int idx = headerIndexMap[colName];
                    if (idx < columns.size()) {
                        value = columns[idx];
                    }
                }

                if (colName == "Entity") {
                    if (fileName == "NrDlPdcpRxStats.txt") value = "UE PDCP Rxed";
                    else if (fileName == "NrDlPdcpTxStats.txt") value = "gNB PDCP Txed";
                    else if (fileName == "NrDlRxRlcStats.txt") value = "UE RLC Rxed";
                    else if (fileName == "NrDlTxRlcStats.txt") value = "gNB RLC Txed";
                }

                if (value.empty()) {
                    if (colName == "Entity" || colName == "MsgType") {
                        value = "-"; 
                    } else {
                        value = "-"; 
                    }
                }

                // Time 값은 실수형(double)으로 변환하여 별도로 저장
                if (colName == "Time") {
                    try {
                        timeVal = stod(value);
                    } catch (...) {
                        timeVal = 0.0; // 변환 실패 시 기본값 0.0
                    }
                }

                csvLine += value + (i == targetHeaders.size() - 1 ? "" : ",");
            }
            
            // 구조체 형태로 벡터에 추가
            allRecords.push_back({timeVal, csvLine});
            rowCount++;
        }
        inFile.close();
        cout << "[파싱 성공] " << fileName << " (추가된 행 수: " << rowCount << "개)" << endl;
        successCount++;
    }

    cout << "========== 정렬 작업 시작 ==========" << endl;
    cout << "총 " << allRecords.size() << "개의 행 데이터를 시간(Time)순으로 정렬 중..." << endl;
    
    // C++ algorithm의 sort 함수를 이용하여 timeValue 기준으로 오름차순 정렬
    sort(allRecords.begin(), allRecords.end(), [](const LogRow& a, const LogRow& b) {
        return a.timeValue < b.timeValue;
    });

    cout << "========== 파일 저장 시작 ==========" << endl;
    string outputFileName = "merged_traces.csv";
    ofstream outFile(outputFileName);

    if (!outFile.is_open()) {
        cerr << "[오류] 출력 파일(" << outputFileName << ")을 생성할 수 없습니다." << endl;
        return 1;
    }

    // 1. 헤더 먼저 쓰기
    for (size_t i = 0; i < targetHeaders.size(); ++i) {
        outFile << targetHeaders[i] << (i == targetHeaders.size() - 1 ? "" : ",");
    }
    outFile << "\n";

    // 2. 정렬된 본문 데이터 쓰기
    for (const auto& record : allRecords) {
        outFile << record.csvLine << "\n";
    }
    
    outFile.close();

    cout << "====================================" << endl;
    cout << "작업 완료 요약:" << endl;
    cout << " - 처리된 파일: " << successCount << "개" << endl;
    cout << " - 건너뛴 파일: " << skipCount << "개" << endl;
    cout << " - 전체 기록 수: " << allRecords.size() << "개" << endl;
    cout << " - 최종 저장 파일명: " << outputFileName << " (시간순 정렬 완료)" << endl;

    return 0;
}