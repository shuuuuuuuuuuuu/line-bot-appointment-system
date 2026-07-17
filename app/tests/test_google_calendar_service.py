from unittest import TestCase
from unittest.mock import MagicMock, mock_open, patch

from services.google_calendar_service import get_calendar_service


class GetCalendarServiceTest(TestCase):
    @patch("services.google_calendar_service.build")
    @patch("services.google_calendar_service.Request")
    @patch("services.google_calendar_service.Credentials.from_authorized_user_file")
    @patch("services.google_calendar_service.os.path.exists", return_value=True)
    def test_expired_token_is_refreshed_without_error(
        self,
        _mock_exists,
        mock_from_file,
        mock_request,
        mock_build,
    ):
        credentials = MagicMock()
        credentials.valid = False
        credentials.expired = True
        credentials.refresh_token = "refresh-token"
        credentials.to_json.return_value = '{"token":"new-token"}'
        mock_from_file.return_value = credentials

        calendar_service = MagicMock()
        mock_build.return_value = calendar_service

        with patch(
            "services.google_calendar_service.open",
            mock_open(),
            create=True,
        ) as mocked_open:
            service_generator = get_calendar_service()
            result = next(service_generator)
            service_generator.close()

        self.assertIs(result, calendar_service)
        credentials.refresh.assert_called_once_with(mock_request.return_value)
        mocked_open.assert_called_once_with("token.json", "w")
        mocked_open().write.assert_called_once_with('{"token":"new-token"}')
        mock_build.assert_called_once_with(
            "calendar",
            "v3",
            credentials=credentials,
        )
