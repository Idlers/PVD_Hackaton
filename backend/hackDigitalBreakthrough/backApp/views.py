import os
import zipfile
from django.conf import settings
from rest_framework.decorators import action
from rest_framework import viewsets, status
from rest_framework.response import Response
import pandas as pd
from .models import Client
from .serializers import ClientSerializer

class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer

    @action(detail=False, methods=['post'], url_path='upload-zip')
    def upload_zip(self, request):
        # Получаем ZIP файл из запроса
        zip_file = request.FILES.get('file')
        if not zip_file:
            return Response({"error": "Файл не найден."}, status=status.HTTP_400_BAD_REQUEST)

        # Папка для сохранения распакованных файлов
        extraction_dir = os.path.join(settings.MEDIA_ROOT, 'uploaded_files')
        os.makedirs(extraction_dir, exist_ok=True)

        # Распаковка архива
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(extraction_dir)

        # Пути к нужным папкам
        marketing_folder = os.path.join(extraction_dir, 'Выгрузка_маркетинговые списки')
        interests_folder = os.path.join(extraction_dir, 'Выгрузки_интересы+обращения+объемы перевозок')

        # Проверяем наличие нужных папок после распаковки
        if not os.path.exists(marketing_folder) or not os.path.exists(interests_folder):
            return Response({"error": "Не найдены необходимые папки в архиве."}, status=status.HTTP_400_BAD_REQUEST)

        # Извлечение уникальных значений "Город фактический" из файлов папки маркетинговых списков
        unique_cities = set()
        for file_name in os.listdir(marketing_folder):
            file_path = os.path.join(marketing_folder, file_name)
            if file_path.endswith('.xlsx'):
                df = pd.read_excel(file_path)
                unique_cities.update(df['Город фактический'].dropna().unique())

        return Response({"cities": list(unique_cities)}, status=status.HTTP_200_OK)

    def list(self, request, *args, **kwargs):
        # Дополнительная логика фильтрации по запросу
        # queryset = super().get_queryset()
        filters = {
            'isMSP': request.query_params.get('isMSP'),
            'companySize': request.query_params.get('companySile'),
            'cityActual': request.query_params.get('cityActual'),
            'cityLegal': request.query_params.get('cityLegal'),
            'shipper': request.query_params.get('shipper'),
            'consignee': request.query_params.get('consignee')
        }

        # Подготовка папок для передачи в ML-модель
        extraction_dir = os.path.join(settings.MEDIA_ROOT, 'uploaded_files')
        marketing_folder = os.path.join(extraction_dir, 'выгрузка_маркетинговые списки')
        interests_folder = os.path.join(extraction_dir, 'выгрузки_интересы+обращения+объемы перевозок')

        # здесь будет отправка фильтров в модель
        ml_predictions = self.get_ml_predictions(filters, marketing_folder, interests_folder)
        # Извлекаем ID и шанс ухода из результата ML-модели
        client_data = []
        for prediction in ml_predictions:
            client_id = prediction['id']
            living_chance = prediction['livingChance']

            # Ищем ID по нескольким Excel-файлам и извлекаем уникальные записи
            client_info = self.find_client_info_in_excels(client_id, marketing_folder)
            if client_info:
                # Подготовка данных для записи в БД
                client_data.append({
                    'id': client_id,
                    'OKVED2Name': client_info['OKVED2Name'],
                    'livingChance': living_chance
                })
        # Сохранение данных в БД (при необходимости обновления записей, используем update_or_create)
        for data in client_data:
            Client.objects.update_or_create(id=data['id'], defaults=data)

        # Подготовка и возврат ответа на фронтенд
        queryset = Client.objects.filter(id__in=[d['id'] for d in client_data])
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def get_ml_predictions(self, filters, marketing_folder, interests_folder):
        # Симулируем отправку данных в ML-модель и получение результатов
        # Реализуйте здесь вызов вашей ML-модели
        # Предположим, модель возвращает [{"id": 123, "livingChance": 0.75}, ...]
        return [
            {'id': 1, 'livingChance': 0.85},
            {'id': 2, 'livingChance': 0.60},
            # Добавьте здесь другие данные
        ]

    def find_client_info_in_excels(self, client_id, folder):
        # Путь к вашим Excel файлам
        excel_files = []  # Замените на ваши файлы
        unique_client_info = {}

        for file_path in excel_files:
            df = pd.read_excel(file_path)

            # Проверяем, есть ли ID клиента в файле
            matching_rows = df[df['ID'] == client_id]
            if not matching_rows.empty:
                # Получаем первую найденную строку с данным ID
                unique_client_info = {
                    'ID': matching_rows.iloc[0]['ID'],
                    'OKVED2Name': matching_rows.iloc[0]['ОКВЭД2.Наименование']
                }
                break

        # Возвращаем уникальное совпадение
        return unique_client_info if unique_client_info else None
