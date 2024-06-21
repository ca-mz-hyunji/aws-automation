# AutoReport 구축 가이드

## 구성 파일 설명
| File      | Description |
| ----------- | ----------- |
| AccountCheck      | 고객사의 Account에 설정된 AssumeRole의 세션 토큰 받음 & PMS의 업무현황을 수집    |
| GetResources   | Boto3를 통해 서비스의 자원 Describe        |
| PlacingPPT   | 수집한 데이터를 가공하여 PPT로 제작        |
| AssumeRole.yaml  |고객 Account에 AssumeRole을 설정하는 CloudFormation 템플릿.        |
| Python_Layers   | 코드에 import 되어있는 확장 모듈들, Lambda Layer로 추가해야 함.        |
| AutoReport-table.txt   | Report 데이터용 테이블 dump 파일        |

## 전체 구조 설명

1. EventBridge의 Rule로 매월 말일 18:00 KST에 [Lambda] AccountCheck Function을 구동하는 Cron이 동작한다.
2. [Lambda] Account Check 코드에서 수집할(자동 보고서를 생성할) Account를 확인하고 AssumeRole의 세션 토큰을 받아 [Lambda] GetResources Function으로 invoke 한다.
3. [Lambda] GetResources 코드에서 각 고객사의 세션으로 Boto3 API 인증해 데이터를 수집하고, DB에 당월 데이터를 저장한다. 그리고 DB에서 이전 저장한 데이터를 받아 [Lambda] PlacingPPT Function으로 invoke한다.
4. [Lambda] PlacingPPT 코드에서 pptx 모듈을 통해 수집된 데이터를 PPT 형식으로 가공하고 S3에 저장한다.

## 구축 인프라
- EventBridge Rule : Crony - 00 09 L * ? *
- Policy : AccountCheck Function Role에 있어야 함
    ```
    {
        "Version": "2012-10-17",
        "Statement": {
            "Effect": "Allow",
            "Action": "sts:AssumeRole",
            "Resource": "arn:aws:iam::*:role/mzc-assumerole"
        }
    }
    ```
- DB: 첨부된 AutoReport-table.txt 참고해 생성
- Lambda Function: Runtime=python3.8 / Memory=128 / Timeout=900 (Function 구동에 필요한 모듈은 런타임 맞춰 Layer 구성하여 각 Function에 추가 필요=Layers 폴더에 있음.)
- S3: 구동 lambda 위치의 Region  Form Put/get, 최종가공물 Put/Get 용도로 생성 필요.

## 수정 사항

> 코드: 각 코드 문서 내 "FIX_INPUT" 부분 수정
- AccountCheck > lambda_function.py
- GetResources > module > dbModule.py
- GetResources > library > trusted_advisor_target.json
- PlacingPPT > report_automation.py

> CFN: FIX_INPUT_ 뒤에 있는 값 입력
- Master Account Id: 구동하는 Account의 Id 입력
- ExternalId: AssumeRole 확인할 키값

> DB: 첨부된 Table을 Database에 import
- report_cycle: 분기 | 월간
- msp_level: Standard | Premium