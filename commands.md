```bash
# Запуск Terraform и проверка конфигурации
terraform init
terraform validate
```

```bash
# Создание ключа сервисного аккаунта и базы YDB
terraform apply \
  -target=yandex_iam_service_account_static_access_key.provisioner \
  -target=yandex_ydb_database_serverless.main
```

```bash
# Подготовка плана и развёртывание системы
terraform plan -out=deploy.tfplan
terraform apply deploy.tfplan
```

```bash
# Получение адреса API и списка архивов
API="$(terraform output -raw api_url)"
echo "$API"
curl -fsS "$API/archives" | python3 -m json.tool
```

```bash
# Отправка задания на архивирование (HTTP 202)
curl -i "$API/tasks" \
  -H 'Content-Type: application/json' \
  -d '{"name":"demo.txt","url":"https://www.rfc-editor.org/rfc/rfc9562.txt"}'
```

```bash
# Поиск готового архива в списке
curl -fsS "$API/archives" | python3 -m json.tool
```

```bash
# Получение описания архива по ключу из списка
read -rp "Ключ архива: " KEY
curl -fsS "$API/archives/$KEY" | python3 -m json.tool
```

```bash
# Скачивание ZIP и просмотр содержимого
curl -fsS "$API/download/$KEY" -o /tmp/vvot27-demo.zip
unzip -l /tmp/vvot27-demo.zip
```

```bash
# Сравнение файла из архива с оригиналом
curl -fLsS https://www.rfc-editor.org/rfc/rfc9562.txt -o /tmp/vvot27-original.txt
unzip -p /tmp/vvot27-demo.zip demo.txt | cmp - /tmp/vvot27-original.txt && echo "Файлы совпадают"
```

```bash
# Проверка запроса без обязательного поля url (HTTP 400)
curl -i "$API/tasks" \
  -H 'Content-Type: application/json' \
  -d '{"name":"demo.txt"}'
```

```bash
# Удаление ресурсов и архивов
terraform destroy
```

```bash
# Проверка состояния после удаления
terraform state list
```
